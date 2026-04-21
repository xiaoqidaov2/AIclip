from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseDetectFacesMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def detect_faces(
        self,
        project_path: str,
        media_path: Optional[str] = None,
        timestamps: Optional[List[float]] = None,
        sample_interval: float = 1.0,
        max_frames: int = 30,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_face_size: int = 30,
    ) -> Dict[str, Any]:

        try:

            import cv2

        except ImportError:

            return self._failure(
                "detect_faces",
                "opencv-python is required. Run: pip install opencv-python",
                code="dependency.missing",
            )

        project, failure = self._load(project_path)

        if failure:

            return failure

        source_path = self._resolve_media_path(project, media_path, project_path)

        if source_path is None:

            return self._failure(
                "detect_faces",
                "No media source found in project",
                code="media.source.missing",
                path=str(Path(project_path)),
            )

        cap = cv2.VideoCapture(str(source_path))

        if not cap.isOpened():

            return self._failure(
                "detect_faces",
                f"Cannot open video: {source_path}",
                code="media.open_failed",
                path=str(source_path),
            )

        try:

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            duration = total_frames / fps if fps > 0 else 0.0

            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if timestamps:

                sample_times = [
                    float(t) for t in timestamps if 0.0 <= float(t) <= duration
                ]

            else:

                if sample_interval <= 0:

                    sample_interval = 1.0

                sample_times = []

                t = 0.0

                while t <= duration and len(sample_times) < max_frames:

                    sample_times.append(t)

                    t += sample_interval

            cv2_data = getattr(cv2, "data", None)

            cascade_dir = getattr(cv2_data, "haarcascades", "")

            cascade_path = cascade_dir + "haarcascade_frontalface_default.xml"

            detector = cv2.CascadeClassifier(cascade_path)

            frame_results: List[Dict[str, Any]] = []

            total_faces = 0

            for ts in sample_times:

                frame_index = int(ts * fps)

                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

                ret, frame = cap.read()

                if not ret:

                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                faces = detector.detectMultiScale(
                    gray,
                    scaleFactor=scale_factor,
                    minNeighbors=min_neighbors,
                    minSize=(min_face_size, min_face_size),
                )

                face_list: List[Dict[str, Any]] = []

                for x, y, w, h in (faces if len(faces) > 0 else []):

                    face_list.append(
                        {
                            "x": int(x),
                            "y": int(y),
                            "w": int(w),
                            "h": int(h),
                            "cx": int(x + w // 2),
                            "cy": int(y + h // 2),
                            "norm_x": round(x / video_width, 4) if video_width else 0,
                            "norm_y": round(y / video_height, 4) if video_height else 0,
                            "norm_w": round(w / video_width, 4) if video_width else 0,
                            "norm_h": round(h / video_height, 4) if video_height else 0,
                        }
                    )

                total_faces += len(face_list)

                frame_results.append(
                    {
                        "timestamp": round(ts, 3),
                        "frame_index": frame_index,
                        "face_count": len(face_list),
                        "faces": face_list,
                    }
                )

        finally:

            cap.release()

        frames_with_faces = sum(1 for f in frame_results if f["face_count"] > 0)

        project.metadata["detected_faces"] = frame_results

        saved_path = self.store.save(project, project_path)

        return ToolResult(
            ok=True,
            status="ok",
            code="faces.detected",
            message=f"Detected {total_faces} face(s) across {len(frame_results)} sampled frame(s)",
            operation="detect_faces",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(passed=True),
            render_state=RenderState(ready=True, blockers=[]),
            artifacts=[
                ArtifactRef(type="media", path=str(source_path)),
                ArtifactRef(type="project", path=str(saved_path)),
            ],
            state={
                "media_path": str(source_path),
                "project_path": str(saved_path),
                "video_width": video_width,
                "video_height": video_height,
                "duration": round(duration, 3),
                "fps": round(fps, 3),
                "frames_sampled": len(frame_results),
                "frames_with_faces": frames_with_faces,
                "total_faces_detected": total_faces,
            },
            payload={
                "video_width": video_width,
                "video_height": video_height,
                "duration": round(duration, 3),
                "fps": round(fps, 3),
                "frames": frame_results,
                "total_faces_detected": total_faces,
                "frames_with_faces": frames_with_faces,
            },
            summary=f"Found faces in {frames_with_faces}/{len(frame_results)} frames, {total_faces} total detections",
        ).to_dict()

    # ------------------------------------------------------------------

    # Subtitle animation helpers (used by render_project)

    # ------------------------------------------------------------------
