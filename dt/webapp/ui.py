from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, send_from_directory


def create_ui_blueprint(ui_dir: Path, url_prefix: str = "") -> Blueprint:
    bp = Blueprint("ui", __name__, url_prefix=url_prefix)

    def _index_missing() -> Response:
        return Response(
            "UI not built. Build the Svelte UI and place the output in the configured ui_dir.",
            status=503,
            mimetype="text/plain",
        )

    @bp.route("/", defaults={"path": ""})
    @bp.route("/<path:path>")
    def ui(path: str):
        index_path = ui_dir / "index.html"
        if not index_path.exists():
            return _index_missing()

        if path:
            candidate = ui_dir / path
            if candidate.exists() and candidate.is_file():
                return send_from_directory(ui_dir, path)

        return send_from_directory(ui_dir, "index.html")

    return bp


def default_ui_dir() -> Path:
    return Path(__file__).resolve().parent / "static" / "ui"
