from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.archive_source_documents import (
    ArchiveSourceIntegrityError,
    media_type_for_path,
    normalize_relative_path,
    resolve_archive_source_document,
)


def stable_key(data: bytes, ordinal: int = 1) -> str:
    return f"nephro-archive-v1:{hashlib.sha256(data).hexdigest()}:{ordinal}"


def test_resolve_archive_source_document_checks_hash(tmp_path: Path):
    data = b"old word document"
    source = tmp_path / "folder" / "patient.doc"
    source.parent.mkdir()
    source.write_bytes(data)

    resolved = resolve_archive_source_document(
        r"folder\patient.doc",
        stable_key(data),
        root=tmp_path,
    )
    assert resolved == source.resolve()
    assert media_type_for_path(resolved) == "application/msword"


def test_resolve_archive_source_document_rejects_changed_file(tmp_path: Path):
    source = tmp_path / "patient.docx"
    source.write_bytes(b"changed")

    with pytest.raises(ArchiveSourceIntegrityError, match="контрольная сумма"):
        resolve_archive_source_document(
            "patient.docx",
            stable_key(b"original"),
            root=tmp_path,
        )


def test_archive_relative_path_rejects_escape():
    assert normalize_relative_path(r"folder\patient.doc") == "folder/patient.doc"
    with pytest.raises(ArchiveSourceIntegrityError):
        normalize_relative_path(r"..\patient.doc")
    with pytest.raises(ArchiveSourceIntegrityError):
        normalize_relative_path(r"D:\patient.doc")
