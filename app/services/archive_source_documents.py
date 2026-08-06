from __future__ import annotations

"""Безопасный доступ к исходным документам архивных консультаций."""

import hashlib
import mimetypes
import os
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE_ROOT = (
    PROJECT_ROOT.parent / "nephro_consultation_preparer" / "medical_archive"
)
ALLOWED_EXTENSIONS = {".doc", ".docx", ".pdf"}
STABLE_KEY_RE = re.compile(r"^nephro-archive-v1:([0-9a-f]{64}):(\d+)$")


class ArchiveSourceDocumentError(RuntimeError):
    """Базовая ошибка доступа к исходному документу."""


class ArchiveSourceNotConfiguredError(ArchiveSourceDocumentError):
    pass


class ArchiveSourceNotFoundError(ArchiveSourceDocumentError):
    pass


class ArchiveSourceIntegrityError(ArchiveSourceDocumentError):
    pass


def get_archive_documents_root() -> Path:
    """Возвращает корень архива из env или соседнего проекта парсера."""
    raw = os.getenv("ARCHIVE_DOCUMENTS_ROOT", "").strip()
    root = Path(raw).expanduser() if raw else DEFAULT_ARCHIVE_ROOT
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    root = root.resolve()
    if not root.is_dir():
        raise ArchiveSourceNotConfiguredError(
            "Не найдена папка исходных документов. "
            "Задайте ARCHIVE_DOCUMENTS_ROOT в .env."
        )
    return root


def normalize_relative_path(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    text = re.sub(r"/+", "/", text)
    if not text:
        raise ArchiveSourceNotFoundError("У приёма не сохранён путь к исходному документу")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ArchiveSourceIntegrityError("В базе сохранён не относительный путь")
    parts = [part for part in text.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ArchiveSourceIntegrityError("Недопустимый путь исходного документа")
    return "/".join(parts)


def expected_sha256_from_import_key(import_key: str | None) -> str:
    match = STABLE_KEY_RE.fullmatch(str(import_key or "").strip().lower())
    if not match:
        raise ArchiveSourceIntegrityError(
            "У архивного приёма нет устойчивого ключа для проверки исходного файла"
        )
    return match.group(1)


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_archive_source_document(
    relative_path: str,
    import_key: str | None,
    *,
    root: Path | None = None,
) -> Path:
    """Находит файл, запрещает выход из архива и проверяет SHA-256."""
    archive_root = (root or get_archive_documents_root()).resolve()
    normalized = normalize_relative_path(relative_path)
    candidate = archive_root.joinpath(*normalized.split("/")).resolve()

    try:
        candidate.relative_to(archive_root)
    except ValueError as exc:
        raise ArchiveSourceIntegrityError(
            "Путь исходного документа выходит за пределы архива"
        ) from exc

    if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ArchiveSourceIntegrityError(
            f"Недопустимый тип исходного документа: {candidate.suffix or 'без расширения'}"
        )
    if not candidate.is_file():
        raise ArchiveSourceNotFoundError(f"Исходный документ не найден: {normalized}")

    expected_sha = expected_sha256_from_import_key(import_key)
    actual_sha = calculate_sha256(candidate)
    if actual_sha.lower() != expected_sha:
        raise ArchiveSourceIntegrityError(
            "Исходный документ найден, но его контрольная сумма не совпадает с импортированной"
        )
    return candidate


def media_type_for_path(path: Path) -> str:
    known = {
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
    }
    return (
        known.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )
