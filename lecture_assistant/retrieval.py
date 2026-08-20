"""Lightweight keyword-based retrieval for citation-grounded Q&A.

No embeddings/vector DB dependency: notes get split into overlapping chunks,
and a question is matched against chunks via term-frequency scoring. Good
enough for personal lecture-note collections and keeps the whole app
dependency-light (just Flask + Anthropic).
"""

from __future__ import annotations

import dataclasses
import math
import re
from collections import Counter

from file_store import NoteFile

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

_STOPWORDS = {
    "der", "die", "das", "und", "ist", "im", "in", "von", "zu", "den", "mit",
    "ein", "eine", "einer", "eines", "einem", "einen", "wie", "was", "wann",
    "wer", "auf", "für", "sich", "sind", "war", "waren", "auch", "als", "an",
    "dem", "des", "es", "nicht", "wird", "werden", "hat", "haben", "oder",
    "aber", "dass", "wo", "man", "noch", "nur", "kann", "können", "über",
    "the", "and", "for", "are", "was", "were",
}


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-zA-ZäöüÄÖÜß]{3,}", text.lower()) if w not in _STOPWORDS]


@dataclasses.dataclass
class Chunk:
    file_name: str
    index: int
    line_start: int
    line_end: int
    text: str

    @property
    def label(self) -> str:
        return f"{self.file_name}, Abschnitt {self.index + 1} (Zeilen {self.line_start}-{self.line_end})"


def chunk_note(note: NoteFile) -> list[Chunk]:
    lines = note.text.splitlines() or [note.text]
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_len = 0
    start_line = 1
    idx = 0

    def flush(end_line: int) -> None:
        nonlocal idx
        if not buf:
            return
        chunks.append(Chunk(note.name, idx, start_line, end_line, "\n".join(buf)))
        idx += 1

    for i, line in enumerate(lines, start=1):
        buf.append(line)
        buf_len += len(line) + 1
        if buf_len >= CHUNK_SIZE:
            flush(i)
            tail: list[str] = []
            tail_len = 0
            while buf and tail_len < CHUNK_OVERLAP:
                l = buf.pop()
                tail.insert(0, l)
                tail_len += len(l) + 1
            buf = tail
            buf_len = tail_len
            start_line = max(1, i - len(tail) + 1)

    if buf:
        flush(len(lines))
    if not chunks:
        chunks = [Chunk(note.name, 0, 1, len(lines), note.text)]
    return chunks


def build_index(notes: list[NoteFile]) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for note in notes:
        all_chunks.extend(chunk_note(note))
    return all_chunks


def search(chunks: list[Chunk], query: str, top_k: int = 6) -> list[Chunk]:
    query_terms = Counter(_tokenize(query))
    if not query_terms:
        return chunks[:top_k]

    scored: list[tuple[float, Chunk]] = []
    for chunk in chunks:
        term_counts = Counter(_tokenize(chunk.text))
        if not term_counts:
            continue
        score = sum(
            qcount * (1 + math.log(term_counts[term]))
            for term, qcount in query_terms.items()
            if term in term_counts
        )
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [c for _, c in scored[:top_k]]

    if not top:
        # No keyword overlap at all: still hand Claude one chunk per file so
        # it can honestly say "not covered by the notes" instead of guessing.
        seen: set[str] = set()
        for c in chunks:
            if c.file_name not in seen:
                top.append(c)
                seen.add(c.file_name)
            if len(top) >= top_k:
                break
    return top
