from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_local_tender_storage(tmp_path, monkeypatch):
    """Keep API tests from leaving tender uploads or analyses in the user data directory."""
    from app.api.document_store import document_store

    monkeypatch.setattr(document_store, "_root", tmp_path / "tender_workspace")
