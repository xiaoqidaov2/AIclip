# Animation, Overlay, and Clip Editing TODO

Goal
- Turn Anime.js code into a transparent overlay asset.
- Place the overlay back onto a screen region in the video timeline.
- Add a real clip editing tool that can change the visible placement/size of a clip.

MVP scope
- Generate a transparent PNG overlay from generated Anime.js output.
- Store the generated asset in the project workspace and register it in the project.
- Add the overlay as a normal project clip on a dedicated overlay track.
- Update clip `transform` values with editor-style controls: `x`, `y`, `scale`, `opacity`.

Planned tools
- `generate_animejs_overlay_asset`
- `apply_overlay_to_screen`
- `set_project_clip_transform`

Implementation notes
- Keep the rendering path inside the existing `ProjectTool` and `render_project` pipeline.
- Do not invent a separate project model for overlays.
- Reuse `Asset`, `Clip`, `Track`, and `Clip.transform`.
- Keep Anime.js execution isolated so the Python runtime only receives exported frames/files.

Out of scope for MVP
- Full keyframe editor.
- Perspective corner pin tracking.
- GPU-accelerated compositing.
- Browser UI timeline editing.
