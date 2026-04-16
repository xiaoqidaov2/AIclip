from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.editor_core.contracts import ArtifactRef, RenderState, ToolResult, ValidationSnapshot
from src.editor_core.store import ProjectStore
from src.net_asset.downloader import download_file
from src.net_asset.freesound import FreesoundProvider
from src.net_asset.pexels import PexelsProvider
from src.net_asset.pixabay import PixabayProvider
from src.net_asset.providers import AssetResult, BaseProvider

_DEFAULT_DEST = "tmp"


class NetAssetTool:
    """LLM-facing tools for searching and downloading web stock assets."""

    def __init__(self) -> None:
        self._store = ProjectStore()
        self._providers: Dict[str, BaseProvider] = {
            "pexels": PexelsProvider(),
            "pixabay": PixabayProvider(),
            "freesound": FreesoundProvider(),
        }

    # ------------------------------------------------------------------
    # Public tool methods
    # ------------------------------------------------------------------

    def search_net_asset(
        self,
        query: str,
        media_type: str = "video",
        provider: str = "auto",
        per_page: int = 8,
        orientation: str = "",
    ) -> Dict[str, Any]:
        """Search online stock libraries for free-to-use media assets."""
        per_page = max(1, min(per_page, 80))

        chosen = self._pick_provider(provider, media_type)
        if not chosen:
            available = [n for n, p in self._providers.items() if p.is_available()]
            msg = (
                f"No API key configured for provider '{provider}' "
                f"with media_type='{media_type}'. "
                f"Available providers: {available or 'none'}. "
                "Set the relevant API key in .env."
            )
            return ToolResult(
                ok=False,
                status="error",
                code="net_asset.search.no_provider",
                message=msg,
                operation="search_net_asset",
                validation=ValidationSnapshot(passed=False, errors=[msg]),
                error=msg,
                summary=msg,
            ).to_dict()

        try:
            results: List[AssetResult] = chosen.search(
                query=query,
                media_type=media_type,
                per_page=per_page,
                orientation=orientation,
            )
        except Exception as exc:
            msg = str(exc)
            return ToolResult(
                ok=False,
                status="error",
                code="net_asset.search.failed",
                message=msg,
                operation="search_net_asset",
                error=msg,
                summary=msg,
            ).to_dict()

        return ToolResult(
            ok=True,
            status="ok",
            code="net_asset.search.ok",
            message=f"Found {len(results)} results from {chosen.name}",
            operation="search_net_asset",
            state={
                "provider_used": chosen.name,
                "total_returned": len(results),
                "query": query,
                "media_type": media_type,
            },
            payload={"results": [_to_dict(r) for r in results]},
            summary=f"Found {len(results)} {media_type} result(s) for '{query}' via {chosen.name}",
        ).to_dict()

    def download_net_asset(
        self,
        download_url: str,
        project_path: str = "",
        save_to: str = "",
        filename: str = "",
        attribution: str = "",
    ) -> Dict[str, Any]:
        """Download a stock asset to the local filesystem.

        Call this after ``search_net_asset`` once the desired result has been
        identified.  Pass *download_url* and *attribution* from the search
        result object.  After downloading, register the file in the project
        via ``add_project_asset`` using the returned ``local_path``.
        """
        workspace_media_rel = ""
        if project_path:
            workspace = self._store.workspace_for_project(project_path)
            workspace.ensure()
            dest = workspace.media_dir
        else:
            dest = Path(save_to) if save_to else Path(_DEFAULT_DEST)

        try:
            local_path = download_file(download_url, dest_dir=dest, filename=filename or None)
            if project_path:
                workspace = self._store.workspace_for_project(project_path)
                workspace_media_rel = workspace.to_storage_path(local_path)
        except Exception as exc:
            msg = str(exc)
            return ToolResult(
                ok=False,
                status="error",
                code="net_asset.download.failed",
                message=msg,
                operation="download_net_asset",
                error=msg,
                summary=msg,
            ).to_dict()

        return ToolResult(
            ok=True,
            status="ok",
            code="net_asset.download.ok",
            message=f"Downloaded {local_path.name}",
            operation="download_net_asset",
            artifacts=[ArtifactRef(type="media", path=str(local_path), label=local_path.name)],
            state={
                "local_path": str(local_path),
                "project_asset_path": workspace_media_rel or str(local_path),
                "filename": local_path.name,
                "attribution": attribution,
            },
            summary=f"Downloaded {local_path.name} to {local_path.parent}",
        ).to_dict()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_provider(self, provider: str, media_type: str) -> Optional[BaseProvider]:
        if provider != "auto":
            p = self._providers.get(provider)
            return p if (p and p.is_available()) else None

        # "auto" strategy: prefer provider by media type
        if media_type == "audio":
            order = ["freesound", "pixabay"]
        else:
            order = ["pexels", "pixabay"]

        for name in order:
            p = self._providers[name]
            if p.is_available():
                return p
        return None


def _to_dict(result: AssetResult) -> Dict[str, Any]:
    d = asdict(result)
    # Trim tags to avoid bloating the LLM context
    d["tags"] = d.get("tags", [])[:8]
    return d
