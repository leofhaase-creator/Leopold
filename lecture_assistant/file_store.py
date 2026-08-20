"""Scans the fixed notes/ folder and extracts text from lecture files."""

from __future__ import annotations

import dataclasses
from pathlib import Path

NOTES_DIR = Path(__file__).parent / "notes"
SUPPORTED_SUFFIXES = {".txt", ".md"}

try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
    SUPPORTED_SUFFIXES = SUPPORTED_SUFFIXES | {".pdf"}
except Exception:
    # pypdf (or one of its native dependencies, e.g. cryptography) may be
    # missing or broken in a given environment - PDF support is optional.
    PDF_SUPPORT = False


@dataclasses.dataclass
class NoteFile:
    name: str
    path: Path
    text: str
    modified: float


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_notes() -> list[NoteFile]:
    """Rescans the notes/ folder from disk on every call, so newly dropped
    files show up immediately without restarting the server."""
    NOTES_DIR.mkdir(exist_ok=True)
    notes = []
    for path in sorted(NOTES_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            text = _read_pdf(path) if path.suffix.lower() == ".pdf" else _read_text(path)
        except Exception:
            continue
        text = text.strip()
        if not text:
            continue
        notes.append(NoteFile(name=path.name, path=path, text=text, modified=path.stat().st_mtime))
    return notes


def get_note(name: str) -> NoteFile | None:
    for note in load_notes():
        if note.name == name:
            return note
    return None
