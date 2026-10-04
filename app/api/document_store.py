from __future__ import annotations

import mimetypes
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".jfif", ".png", ".tif", ".tiff", ".bmp", ".avif"}


class StoredDocument:
    def __init__(self, document_id: str, path: Path, filename: str, media_type: str) -> None:
        self.document_id = document_id
        self.path = path
        self.filename = filename
        self.media_type = media_type


class LocalDocumentStore:
    """Small local persistence boundary for source files and reusable analysis JSON."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path(__file__).resolve().parents[2] / "outputs/tender_workspace")

    async def save_upload(self, upload: UploadFile, *, max_bytes: int) -> StoredDocument:
        original_name = (upload.filename or "").replace("\\", "/").split("/")[-1]
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError("Unsupported file format")
        data = await upload.read(max_bytes + 1)
        if not data:
            raise ValueError("Uploaded document is empty")
        if len(data) > max_bytes:
            raise ValueError(f"Document exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
        document_id = uuid4().hex
        record_dir = self._root / document_id
        record_dir.mkdir(parents=True, exist_ok=True)
        path = record_dir / f"source{suffix}"
        path.write_bytes(data)
        # The client-provided Content-Type is untrusted; derive the inline response type from the
        # allow-listed filename extension so an uploaded script cannot be served as active HTML.
        media_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        stored = StoredDocument(document_id, path, original_name, media_type)
        self._write_json(record_dir / "document.json", {
            "document_id": document_id, "filename": original_name,
            "media_type": media_type, "source_path": path.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return stored

    def get(self, document_id: str) -> StoredDocument | None:
        if len(document_id) != 32 or any(char not in "0123456789abcdef" for char in document_id):
            return None
        metadata_path = self._root / document_id / "document.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            source_name = metadata["source_path"]
            if Path(source_name).name != source_name:
                return None
            path = metadata_path.parent / source_name
            if not path.is_file():
                return None
            return StoredDocument(document_id, path, metadata["filename"], metadata["media_type"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save_analysis(self, document_id: str, *, workflow: str, tender_document: dict,
                      response: dict) -> None:
        if self.get(document_id) is None:
            raise FileNotFoundError("Cannot persist analysis without its source document")
        self._write_json(self._root / document_id / "analysis.json", {
            "schema_version": 1, "workflow": workflow,
            "tender_document": tender_document, "response": response,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        })

    def list_analyses(self) -> list[dict]:
        """List completed local tender results; skip stale and malformed records."""
        if not self._root.is_dir():
            return []
        records = []
        for directory in self._root.iterdir():
            document_id = directory.name
            if not directory.is_dir() or len(document_id) != 32 or any(
                    char not in "0123456789abcdef" for char in document_id):
                continue
            stored = self.get(document_id)
            analysis = self.get_analysis(document_id)
            if stored is None or not analysis or not isinstance(analysis.get("response"), dict):
                continue
            response = analysis["response"]
            document = response.get("document")
            if not isinstance(document, dict) or not isinstance(document.get("page_count"), int):
                continue
            analysis_path = directory / "analysis.json"
            try:
                timestamp = analysis.get("analyzed_at") or datetime.fromtimestamp(
                    analysis_path.stat().st_mtime, timezone.utc).isoformat()
            except OSError:
                continue
            records.append({"document_id": document_id, "filename": stored.filename,
                            "analyzed_at": timestamp, "page_count": document["page_count"],
                            "workflow": analysis.get("workflow", "cdc"), "status": "completed"})
        return sorted(records, key=lambda item: item["analyzed_at"], reverse=True)

    def get_analysis(self, document_id: str) -> dict | None:
        if self.get(document_id) is None:
            return None
        try:
            value = json.loads((self._root / document_id / "analysis.json").read_text(encoding="utf-8"))
            return value if value.get("schema_version") == 1 else None
        except (OSError, ValueError, AttributeError):
            return None

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        temporary_path = path.with_name(path.name + f".{uuid4().hex}.tmp")
        temporary_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary_path, path)


document_store = LocalDocumentStore()
