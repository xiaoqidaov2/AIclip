from __future__ import annotations

import base64
import math
import shutil
import subprocess
from io import BytesIO

import numpy as np

from .project_tool_postparse_common import *


_PLAYWRIGHT_RENDERER_JS = r'''
const { chromium } = require('__PLAYWRIGHT_PKG__');
const path = require('path');
const { pathToFileURL } = require('url');

(async () => {
    const args = JSON.parse(process.argv[2]);
    const { htmlPath, width, height, duration, fps, outputDir, fileStem } = args;

    const totalFrames = Math.max(1, Math.min(Math.round(duration * fps), 96));
    const frameIntervalMs = 1000 / Math.max(fps, 1);

    const browser = await chromium.launch({
        channel: 'msedge',
        headless: true,
    });

    const context = await browser.newContext({
        viewport: { width: parseInt(width), height: parseInt(height) },
        deviceScaleFactor: 1,
    });

    const page = await context.newPage();

    await page.goto(pathToFileURL(htmlPath).href, {
        waitUntil: 'networkidle',
        timeout: 30000,
    });

    // Wait for JS and Anime.js to initialize
    await page.waitForTimeout(800);

    const framePaths = [];
    for (let i = 0; i < totalFrames; i++) {
        const frameFile = path.join(outputDir, `${fileStem}_frame_${String(i).padStart(4, '0')}.png`);
        await page.screenshot({
            path: frameFile,
            type: 'png',
            omitBackground: true,
        });
        framePaths.push(frameFile);

        if (i < totalFrames - 1) {
            await page.waitForTimeout(frameIntervalMs);
        }
    }

    await browser.close();

    console.log(JSON.stringify({ success: true, frames: framePaths }));
})();
'''


class ProjectToolPostParseGenerateAnimejsOverlayAssetMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _overlay_file_stem(self, asset_id: str, code: str) -> str:
        digest = hashlib.sha1(code.encode("utf-8")).hexdigest()[:10]
        safe_asset_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in asset_id).strip("_") or "overlay"
        return f"{safe_asset_id}_{digest}"

    def _overlay_style_profile(self, asset_id: str, label: str, code: str, width: int, height: int) -> Dict[str, Any]:
        """Extract visual style from LLM-generated JS code instead of using hash.

        Parses colors, shapes, and animation intent from the code to produce
        a style profile that matches what the LLM actually described.
        """
        import re

        width = max(1, int(width))
        height = max(1, int(height))
        code_lower = code.lower()

        # --- Extract colors from the code ---
        colors_found: list[tuple[int, int, int, int]] = []

        # Hex colors #RGB #RRGGBB #RRGGBBAA
        for m in re.finditer(r'#([0-9a-fA-F]{3,8})\b', code):
            hx = m.group(1)
            if len(hx) == 3:
                r, g, b = int(hx[0]*2, 16), int(hx[1]*2, 16), int(hx[2]*2, 16)
                colors_found.append((r, g, b, 255))
            elif len(hx) == 4:
                r, g, b, a = int(hx[0]*2, 16), int(hx[1]*2, 16), int(hx[2]*2, 16), int(hx[3]*2, 16)
                colors_found.append((r, g, b, a))
            elif len(hx) == 6:
                r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
                colors_found.append((r, g, b, 255))
            elif len(hx) == 8:
                r, g, b, a = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16), int(hx[6:8], 16)
                colors_found.append((r, g, b, a))

        # rgb/rgba colors
        for m in re.finditer(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)', code):
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
            a = int(float(m.group(4)) * 255) if m.group(4) else 255
            colors_found.append((r, g, b, a))

        # Deduplicate and pick the most saturated/vibrant color as accent
        if colors_found:
            # Prefer opaque, vibrant colors (high saturation)
            def _saturation(c):
                r, g, b, a = c
                if a < 128:
                    return 0
                mx, mn = max(r, g, b), min(r, g, b)
                return (mx - mn) / max(1, mx)
            colors_found.sort(key=_saturation, reverse=True)
            accent = colors_found[0]
            # Glow is same color but softer
            glow = (accent[0], accent[1], accent[2], 255)
        else:
            # Fallback: derive from label keywords, or use code hash for variety
            accent, glow = self._fallback_color_from_label(label)

        # --- Determine animation style from code content ---
        style_index = self._detect_style_from_code(code_lower, label.lower())

        # --- Center position: use canvas center for most overlays ---
        center_x = 0.5
        center_y = 0.5

        # Adjust based on code positioning hints
        if 'left:50%' in code and 'top:50%' in code:
            center_x, center_y = 0.5, 0.5
        elif 'left:50%' in code:
            center_x = 0.5
        if 'top:40%' in code:
            center_y = 0.4
        elif 'top:60%' in code:
            center_y = 0.6

        # --- Size parameters based on canvas ---
        min_dim = min(width, height)

        # Use code hash to add variety to size/placement when colors are absent
        code_hash = hashlib.sha1(code.encode("utf-8")).digest()

        return {
            "signature": hashlib.sha1(f"{asset_id}:{label}:{code}".encode("utf-8")).hexdigest()[:16],
            "style_index": style_index,
            "accent": accent,
            "glow": glow,
            "phase_offset": (code_hash[5] / 255.0) * math.tau,
            "center_x": center_x,
            "center_y": center_y,
            "orbit_radius": int(min_dim * (0.20 + (code_hash[8] / 255.0) * 0.15)),
            "orbit_jitter": int(min_dim * (0.03 + (code_hash[9] / 255.0) * 0.04)),
            "dot_count": 8 + code_hash[10] % 10,
            "dot_size": max(6, int(min_dim * (0.025 + (code_hash[11] / 255.0) * 0.03))),
            "bar_count": 4 + code_hash[12] % 5,
            "bar_height": max(14, int(min_dim * (0.04 + (code_hash[13] / 255.0) * 0.06))),
            "bar_swing": 0.10 + (code_hash[14] / 255.0) * 0.20,
            "card_width_ratio": 0.18 + (code_hash[15] / 255.0) * 0.22,
            "card_height_ratio": 0.08 + (code_hash[16] / 255.0) * 0.12,
            "card_scale_swing": 0.08 + (code_hash[17] / 255.0) * 0.16,
            "point_count": 3 + code_hash[18] % 5,
            "point_spread": 0.12 + (code_hash[19] / 255.0) * 0.16,
            "size_ratio": 0.08 + (code_hash[0] / 255.0) * 0.08,
        }

    def _render_with_playwright(
        self,
        html_path: Path,
        width: int,
        height: int,
        duration: float,
        fps: float,
        bundle_dir: Path,
        file_stem: str,
    ) -> tuple[list[Image.Image], list[np.ndarray]]:
        """Render animation frames using Playwright headless browser."""
        project_root = Path(__file__).resolve().parents[4]
        playwright_pkg = project_root / "node_modules" / "playwright"
        if not playwright_pkg.exists():
            raise RuntimeError("Playwright Node.js package not found")

        script_path = bundle_dir / f"{file_stem}_renderer.js"
        script_content = _PLAYWRIGHT_RENDERER_JS.replace(
            "__PLAYWRIGHT_PKG__", str(playwright_pkg).replace("\\", "/")
        )
        script_path.write_text(script_content, encoding="utf-8")

        try:
            args = {
                "htmlPath": str(html_path.resolve()),
                "width": int(width),
                "height": int(height),
                "duration": float(duration),
                "fps": float(fps),
                "outputDir": str(bundle_dir),
                "fileStem": file_stem,
            }

            timeout_sec = max(15, int(duration) + 10)

            result = subprocess.run(
                ["node", str(script_path), json.dumps(args)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
                cwd=str(project_root),
            )

            if result.returncode != 0:
                raise RuntimeError(f"Playwright renderer failed: {result.stderr}")

            stdout_lines = result.stdout.strip().split("\n")
            output = json.loads(stdout_lines[-1])
            if not output.get("success"):
                raise RuntimeError("Playwright renderer did not succeed")

            frames: list[Image.Image] = []
            frame_arrays: list[np.ndarray] = []

            for frame_path in output["frames"]:
                img = Image.open(frame_path).convert("RGBA")
                frames.append(img)
                frame_arrays.append(np.array(img))

            if not frames:
                raise RuntimeError("No frames captured")

            # If all frames are fully transparent, the Anime.js code likely did not
            # produce any visible content (e.g. missing elements or CDN failure).
            # Fall back to Python drawing so we never return blank output.
            has_visible_pixels = any(
                np.array(f)[:, :, 3].max() > 0 for f in frames
            )
            if not has_visible_pixels:
                raise RuntimeError("Playwright captured only blank frames")

            return frames, frame_arrays
        finally:
            if script_path.exists():
                script_path.unlink()

    def _render_with_fallback(
        self,
        width: int,
        height: int,
        duration: float,
        fps: float,
        style_profile: Dict[str, Any],
        style_index: int,
    ) -> tuple[list[Image.Image], list[np.ndarray]]:
        """Render frames using existing Python fallback drawing methods."""
        frames: list[Image.Image] = []
        frame_arrays: list[np.ndarray] = []
        total_frames = max(12, int(round(duration * fps)))
        total_frames = min(total_frames, 96)
        for frame_index in range(total_frames):
            phase = ((frame_index / max(1, total_frames - 1)) * math.tau) + float(style_profile["phase_offset"])
            frame = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
            frame_draw = ImageDraw.Draw(frame)
            if style_index == 0:
                self._draw_ring_particles(frame_draw, width, height, phase, style_profile)
            elif style_index == 1:
                self._draw_left_to_right_bars(frame_draw, width, height, phase, style_profile)
            elif style_index == 2:
                self._draw_pulse_cards(frame_draw, width, height, phase, style_profile)
            else:
                self._draw_corner_pop(frame_draw, width, height, phase, style_profile)
            frames.append(frame)
            frame_arrays.append(np.array(frame))
        if not frames:
            blank = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
            frames = [blank]
            frame_arrays = [np.array(blank)]
        return frames, frame_arrays

    def _fallback_color_from_label(self, label: str) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        """Pick colors based on label keywords."""
        label_lower = label.lower()
        color_map = {
            "warning": ((255, 80, 0, 255), (255, 120, 0, 255)),
            "alert": ((255, 80, 0, 255), (255, 120, 0, 255)),
            "danger": ((255, 50, 50, 255), (255, 80, 80, 255)),
            "pain": ((255, 50, 50, 255), (255, 80, 80, 255)),
            "heat": ((255, 100, 50, 255), (255, 150, 80, 255)),
            "hot": ((255, 100, 50, 255), (255, 150, 80, 255)),
            "fire": ((255, 80, 0, 255), (255, 140, 0, 255)),
            "cool": ((79, 195, 247, 255), (128, 222, 234, 255)),
            "cold": ((79, 195, 247, 255), (128, 222, 234, 255)),
            "ice": ((128, 222, 234, 255), (178, 235, 242, 255)),
            "method": ((102, 187, 106, 255), (129, 199, 132, 255)),
            "green": ((102, 187, 106, 255), (129, 199, 132, 255)),
            "success": ((102, 187, 106, 255), (129, 199, 132, 255)),
            "like": ((255, 100, 100, 255), (255, 150, 150, 255)),
            "heart": ((255, 100, 100, 255), (255, 150, 150, 255)),
            "love": ((255, 100, 100, 255), (255, 150, 150, 255)),
            "star": ((255, 200, 50, 255), (255, 230, 100, 255)),
            "gold": ((255, 200, 50, 255), (255, 230, 100, 255)),
            "cta": ((255, 100, 100, 255), (255, 150, 150, 255)),
            "timer": ((79, 195, 247, 255), (128, 222, 234, 255)),
            "clock": ((79, 195, 247, 255), (128, 222, 234, 255)),
            "time": ((79, 195, 247, 255), (128, 222, 234, 255)),
            "red": ((255, 50, 50, 255), (255, 80, 80, 255)),
            "blue": ((33, 150, 243, 255), (66, 165, 245, 255)),
            "purple": ((156, 39, 176, 255), (186, 104, 200, 255)),
            "yellow": ((255, 235, 59, 255), (255, 241, 118, 255)),
            "orange": ((255, 152, 0, 255), (255, 183, 77, 255)),
            "pink": ((233, 30, 99, 255), (240, 98, 146, 255)),
            "cyan": ((0, 188, 212, 255), (77, 208, 225, 255)),
            "white": ((255, 255, 255, 255), (224, 224, 224, 255)),
            "black": ((33, 33, 33, 255), (66, 66, 66, 255)),
        }
        for keyword, colors in color_map.items():
            if keyword in label_lower:
                return colors
        return ((160, 120, 48, 255), (200, 160, 80, 255))

    def _detect_style_from_code(self, code_lower: str, label_lower: str) -> int:
        """Detect which drawing style matches the code intent.

        0 = ring_particles (orbits, circles, rings, particles)
        1 = left_to_right_bars (bars, lines, waves moving horizontally)
        2 = pulse_cards (cards, boxes, rectangles with scale pulse)
        3 = corner_pop (dots, pops, bursts from center)
        """
        # Ring/particles style
        if any(k in code_lower for k in ["ring", "orbit", "circle", "particle", "dot", "ball", "spark"]):
            return 0
        if any(k in label_lower for k in ["ring", "orbit", "particle", "spark", "光环", "粒子", "圆环", "轨道"]):
            return 0

        # Bars style
        if any(k in code_lower for k in ["bar", "line", "wave", "strip", "progress"]):
            return 1
        if any(k in label_lower for k in ["bar", "wave", "line", "strip", "条", "波", "线"]):
            return 1

        # Card/box style
        if any(k in code_lower for k in ["card", "box", "rect", "panel", "badge", "frame"]):
            return 2
        if any(k in label_lower for k in ["card", "box", "badge", "panel", "卡片", "框", "矩形", "面板"]):
            return 2

        # Default: corner_pop (bursts, pops, explosions, triangles, generic pops)
        if any(k in label_lower for k in ["triangle", "三角", "脉冲", "pulse", "glow", "发光", "burst", "爆炸", "pop", "弹出"]):
            return 3
        return 3

    def generate_animejs_overlay_asset(
        self,
        project_path: str,
        asset_id: str,
        code: str,
        width: int = 640,
        height: int = 640,
        duration: float = 3.0,
        fps: float = 30.0,
        label: str = "Anime.js Overlay",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            workspace = self.store.workspace_for_project(project_path)
            workspace.ensure()
            bundle_dir = workspace.media_dir / "generated_overlays"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            file_stem = self._overlay_file_stem(asset_id, code)
            html_path = bundle_dir / f"{file_stem}.html"
            js_path = bundle_dir / f"{file_stem}.js"
            manifest_path = bundle_dir / f"{file_stem}.json"
            preview_path = bundle_dir / f"{file_stem}.gif"
            render_path = bundle_dir / f"{file_stem}.webm"

            js_path.write_text(code, encoding="utf-8")
            html_path.write_text(
                "\n".join(
                    [
                        "<!doctype html>",
                        "<html>",
                        "<head>",
                        "  <meta charset=\"utf-8\">",
                        f"  <title>{label}</title>",
                        f"  <style>",
                        f"    html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; width: {int(width)}px; height: {int(height)}px; }}",
                        f"    #stage {{ width: {int(width)}px; height: {int(height)}px; position: relative; }}",
                        f"  </style>",
                        "  <script src=\"https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.1/anime.min.js\"></script>",
                        "</head>",
                        "<body>",
                        "  <div id=\"stage\"></div>",
                        f"  <script src=\"{js_path.name}\"></script>",
                        "</body>",
                        "</html>",
                    ]
                ),
                encoding="utf-8",
            )

            style_profile = self._overlay_style_profile(asset_id, label, code, width, height)
            style_index = int(style_profile["style_index"])

            frames: list[Image.Image] = []
            frame_arrays: list[np.ndarray] = []
            render_backend = "python_fallback"

            try:
                frames, frame_arrays = self._render_with_playwright(
                    html_path, width, height, duration, fps, bundle_dir, file_stem
                )
                render_backend = "playwright"
            except Exception:
                frames, frame_arrays = self._render_with_fallback(
                    width, height, duration, fps, style_profile, style_index
                )
                render_backend = "python_fallback"

            from moviepy import ImageSequenceClip  # type: ignore[import-untyped]

            sequence_clip = ImageSequenceClip(frame_arrays, fps=max(1.0, float(fps)), with_mask=True)
            try:
                sequence_clip.write_videofile(
                    str(render_path),
                    fps=max(1.0, float(fps)),
                    codec="libvpx-vp9",
                    audio=False,
                    ffmpeg_params=["-pix_fmt", "yuva420p"],
                    logger=None,
                )
            finally:
                close = getattr(sequence_clip, "close", None)
                if callable(close):
                    close()
            frames[0].save(
                preview_path,
                save_all=True,
                append_images=frames[1:],
                duration=max(1, int(round(1000 / max(fps, 1.0)))),
                loop=0,
                disposal=2,
                transparency=0,
            )

            # Encode first frame as base64 for multimodal observation
            preview_frame = frames[0].copy()
            max_preview_size = 512
            width, height = preview_frame.size
            if width > max_preview_size or height > max_preview_size:
                ratio = min(max_preview_size / width, max_preview_size / height)
                new_size = (int(width * ratio), int(height * ratio))
                preview_frame = preview_frame.resize(new_size, Image.Resampling.LANCZOS)
            if preview_frame.mode not in ("RGB", "RGBA"):
                preview_frame = preview_frame.convert("RGBA")
            buffer = BytesIO()
            preview_frame.save(buffer, format="PNG")
            preview_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            # Cleanup temporary frame PNGs generated by Playwright (if any)
            for i in range(96):
                frame_png = bundle_dir / f"{file_stem}_frame_{i:04d}.png"
                if frame_png.exists():
                    frame_png.unlink()
            manifest_path.write_text(
                json.dumps(
                    {
                        "asset_id": asset_id,
                        "label": label,
                        "width": int(width),
                        "height": int(height),
                        "duration": float(duration),
                        "fps": float(fps),
                        "html": html_path.name,
                        "script": js_path.name,
                        "render": render_path.name,
                        "render_format": "webm",
                        "preview": preview_path.name,
                        "preview_format": "gif",
                        "style_index": style_index,
                        "style_signature": style_profile["signature"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            asset = Asset(
                id=asset_id,
                path=workspace.to_storage_path(render_path),
                source="generated",
                media_type="video",
                duration=float(duration),
                metadata={
                    "generator": "animejs",
                    "transparent": True,
                    "size": [int(width), int(height)],
                    "fps": float(fps),
                    "duration": float(duration),
                    "label": label,
                    "style_index": style_index,
                    "style_signature": style_profile["signature"],
                    "animejs_bundle": {
                        "html_path": workspace.to_storage_path(html_path),
                        "script_path": workspace.to_storage_path(js_path),
                        "manifest_path": workspace.to_storage_path(manifest_path),
                        "render_path": workspace.to_storage_path(render_path),
                        "preview_path": workspace.to_storage_path(preview_path),
                    },
                    "visible_preview": True,
                    "animation_format": "webm",
                    "preview_format": "gif",
                    "render_backend": render_backend,
                    "source_hash": hashlib.sha1(code.encode("utf-8")).hexdigest(),
                },
                tags=["overlay", "animejs", "transparent", "animated", f"style_{style_index}"],
            )

            command = AddAssetCommand(asset)
            result = command.execute(project)

            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="generate_animejs_overlay_asset",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(
                        ready=False, blockers=list(result.validation.errors)
                    ),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path)
            report = self.store.validate(project)

            result = ToolResult(
                ok=report.passed,
                status="ok" if report.passed else "warn",
                code="asset.generated",
                message="Anime.js overlay asset generated",
                operation="generate_animejs_overlay_asset",
                project_id=project.id,
                project_version=project.version,
                changes=result.changes,
                validation=ValidationSnapshot(
                    passed=report.passed,
                    warnings=[issue.message for issue in report.warnings],
                    errors=[issue.message for issue in report.errors],
                ),
                render_state=RenderState(
                    ready=report.passed, blockers=[issue.code for issue in report.errors]
                ),
                artifacts=[
                    ArtifactRef(type="project", path=str(saved_path)),
                    ArtifactRef(type="video", path=str(render_path), label="overlay_render"),
                    ArtifactRef(type="image", path=str(preview_path), label="overlay_preview"),
                    ArtifactRef(type="html", path=str(html_path), label="animejs_html"),
                    ArtifactRef(type="script", path=str(js_path), label="animejs_script"),
                    ArtifactRef(type="json", path=str(manifest_path), label="animejs_manifest"),
                ],
                state={
                    **result.state,
                    "project_path": str(saved_path),
                    "asset_id": asset_id,
                    "asset_path": workspace.to_storage_path(render_path),
                    "bundle_manifest_path": workspace.to_storage_path(manifest_path),
                    "style_index": style_index,
                    "style_signature": style_profile["signature"],
                },
                payload=self._project_delta_payload(project, project_path),
                next_actions=["apply_overlay_to_screen"],
                summary=f"Generated Anime.js overlay asset {asset_id}",
            ).to_dict()
            result["_preview_image_b64"] = preview_b64
            result["_preview_image_mime_type"] = "image/png"
            return result

    def _draw_ring_particles(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        center_x = int(width * float(style_profile["center_x"]))
        center_y = int(height * float(style_profile["center_y"]))
        ring_color = tuple(style_profile["glow"])
        dot_color = tuple(style_profile["accent"])
        pulse = 0.75 + 0.25 * math.sin(phase)
        orbit_radius = int(style_profile["orbit_radius"])
        # Background glow for visibility
        glow_radius = max(60, int(orbit_radius * 1.4))
        draw.ellipse(
            (center_x - glow_radius, center_y - glow_radius, center_x + glow_radius, center_y + glow_radius),
            fill=(ring_color[0], ring_color[1], ring_color[2], 32),
        )
        for radius in (max(18, int(orbit_radius * 0.45)), max(32, int(orbit_radius * 0.8)), max(48, int(orbit_radius * 1.15))):
            bbox = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
            draw.ellipse(bbox, outline=ring_color, width=max(3, int(round(6 * pulse))))
        dot_count = int(style_profile["dot_count"])
        dot_size = int(style_profile["dot_size"]) * 2
        orbit_jitter = int(style_profile["orbit_jitter"])
        for index in range(dot_count):
            angle = (math.tau * index) / float(dot_count) + phase
            distance = orbit_radius + int(orbit_jitter * math.sin(phase * 1.7 + index))
            orbit_x = int(center_x + math.cos(angle) * distance)
            orbit_y = int(center_y + math.sin(angle) * (distance + int(orbit_jitter * math.cos(phase * 1.3 + index))))
            radius = int(dot_size + max(1, dot_size // 2) * (0.5 + 0.5 * math.sin(phase + index)))
            draw.ellipse((orbit_x - radius, orbit_y - radius, orbit_x + radius, orbit_y + radius), fill=dot_color)

    def _draw_left_to_right_bars(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        accent = tuple(style_profile["accent"])
        glow = tuple(style_profile["glow"])
        base_y = int(height * float(style_profile["center_y"]))
        bar_count = int(style_profile["bar_count"])
        bar_height = int(style_profile["bar_height"]) * 2
        bar_swing = float(style_profile["bar_swing"])
        # Background strip for visibility
        strip_top = base_y - bar_height
        draw.rounded_rectangle(
            (int(width * 0.05), strip_top, int(width * 0.95), base_y + bar_height + bar_count * 8),
            radius=16, fill=(glow[0], glow[1], glow[2], 40),
        )
        for index in range(bar_count):
            bar_w = int(width * (0.12 + 0.08 * (index + 1)))
            bar_h = int(bar_height + bar_height * 0.6 * math.sin(phase + index))
            offset = int((width + 180) * ((index / max(1.0, float(bar_count))) + bar_swing * math.sin(phase * 1.4 + index)))
            left = offset - bar_w
            top = base_y - bar_h // 2 + index * 8
            draw.rounded_rectangle((left, top, left + bar_w, top + bar_h), radius=8, fill=accent)

    def _draw_pulse_cards(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        card_color = tuple(style_profile["accent"])
        glow_color = tuple(style_profile["glow"])
        center_x = int(width * float(style_profile["center_x"]))
        center_y = int(height * float(style_profile["center_y"]))
        scale = (1.0 - float(style_profile["card_scale_swing"])) + float(style_profile["card_scale_swing"]) * math.sin(phase)
        card_w = int(width * float(style_profile["card_width_ratio"]) * max(0.6, scale))
        card_h = int(height * float(style_profile["card_height_ratio"]) * max(0.6, scale))
        # Background glow for visibility
        glow_r = max(card_w, card_h) + 40
        draw.ellipse(
            (center_x - glow_r, center_y - glow_r, center_x + glow_r, center_y + glow_r),
            fill=(glow_color[0], glow_color[1], glow_color[2], 32),
        )
        draw.rounded_rectangle(
            (center_x - card_w, center_y - card_h, center_x + card_w, center_y + card_h),
            radius=24,
            fill=card_color,
        )
        for radius in (card_w + 20, card_w + 50 + int(style_profile["orbit_jitter"])):
            draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), outline=glow_color, width=4)

    def _draw_corner_pop(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        accent = tuple(style_profile["accent"])
        glow = tuple(style_profile["glow"])
        pop = 0.5 + 0.5 * math.sin(phase)
        size = int(min(width, height) * (float(style_profile["size_ratio"]) + 0.03 * pop)) * 2
        point_count = int(style_profile["point_count"])
        point_spread = float(style_profile["point_spread"])
        center_x = float(style_profile["center_x"])
        center_y = float(style_profile["center_y"])
        # Background glow
        cx, cy = int(width * center_x), int(height * center_y)
        glow_r = int(min(width, height) * point_spread * 2)
        draw.ellipse(
            (cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r),
            fill=(glow[0], glow[1], glow[2], 32),
        )
        for index in range(point_count):
            angle = (math.tau * index) / max(1, point_count)
            # Dots burst outward from center, expanding and contracting with phase
            burst_progress = (math.sin(phase * 2.0 + index * 1.3) + 1.0) / 2.0
            distance = point_spread * burst_progress
            x = int(width * min(0.96, max(0.04, center_x + distance * math.cos(angle))))
            y = int(height * min(0.96, max(0.04, center_y + distance * math.sin(angle))))
            draw.ellipse((x - size, y - size, x + size, y + size), fill=accent)
