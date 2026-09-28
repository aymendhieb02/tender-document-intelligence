from __future__ import annotations

import mimetypes
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import UploadFile


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".jfif", ".png", ".tif", ".tiff", ".bmp", ".avif"}


class StoredDocument:
    def __init__(self, document_id: str, path: Path, filename: str, media_type: str) -> None:
        self.document_id = document_id
        self.path = path
        self.filename = filename
        self.media_type = media_type


class TemporaryDocumentStore:
    """Process-local document access for review; data is removed when the app exits."""

    def __init__(self) -> None:
        self._directory = TemporaryDirectory(prefix="tender-document-intelligence-")
        self._root = Path(self._directory.name)
        self._documents: dict[str, StoredDocument] = {}

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
        path = self._root / f"{document_id}{suffix}"
        path.write_bytes(data)
        media_type = upload.content_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        stored = StoredDocument(document_id, path, original_name, media_type)
        self._documents[document_id] = stored
        return stored

    def get(self, document_id: str) -> StoredDocument | None:
        stored = self._documents.get(document_id)
        return stored if stored and stored.path.is_file() else None


document_store = TemporaryDocumentStore()
