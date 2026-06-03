"""
Processes raw meeting notes using a local GPT4All model.
Returns structured data ready for PDF generation.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    from gpt4all import GPT4All
    GPT4ALL_AVAILABLE = True
except ImportError:
    GPT4ALL_AVAILABLE = False


@dataclass
class ActionItem:
    task: str
    owner: str = ""
    due_date: str = ""


@dataclass
class MeetingData:
    title: str = "Meeting-Protokoll"
    date: str = ""
    time: str = ""
    location: str = ""
    participants: list[str] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)
    summary: str = ""
    topics: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    next_meeting: str = ""


def _build_prompt(raw_notes: str) -> str:
    return f"""Du bist ein professioneller Meeting-Assistent. Analysiere die folgenden Meeting-Notizen und extrahiere die Informationen als JSON.

WICHTIG: Antworte NUR mit einem validen JSON-Objekt, ohne Erklärungen oder Markdown-Code-Blöcke.

Meeting-Notizen:
{raw_notes}

Extrahiere folgende Felder als JSON:
{{
  "title": "Titel des Meetings oder Projekts",
  "date": "Datum des Meetings",
  "time": "Uhrzeit",
  "location": "Ort",
  "participants": ["Name 1", "Name 2"],
  "absent": ["Name falls entschuldigt"],
  "summary": "Zusammenfassung in 2-3 Sätzen",
  "topics": ["Besprochenes Thema 1", "Thema 2"],
  "decisions": ["Entscheidung 1", "Entscheidung 2"],
  "action_items": [
    {{"task": "Aufgabenbeschreibung", "owner": "Verantwortliche Person", "due_date": "Datum oder leer"}}
  ],
  "next_steps": ["Nächster Schritt 1", "Nächster Schritt 2"],
  "open_questions": ["Offene Frage 1"],
  "next_meeting": "Datum und Uhrzeit des nächsten Meetings oder leer"
}}
"""


def _parse_json_from_response(response: str) -> dict:
    response = response.strip()
    # Strip markdown code blocks if model wraps JSON
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
    if match:
        response = match.group(1).strip()
    # Try direct parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    # Find first { ... } block
    brace_match = re.search(r"\{[\s\S]*\}", response)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _fallback_parse(raw_notes: str) -> MeetingData:
    """Basic regex-based fallback when AI is unavailable or fails."""
    data = MeetingData()
    lines = raw_notes.splitlines()

    for line in lines:
        l = line.strip()
        if not l:
            continue
        low = l.lower()
        if low.startswith("datum:"):
            data.date = l.split(":", 1)[1].strip()
        elif low.startswith("uhrzeit:") or low.startswith("zeit:"):
            data.time = l.split(":", 1)[1].strip()
        elif low.startswith("ort:"):
            data.location = l.split(":", 1)[1].strip()
        elif low.startswith("projekt:") or low.startswith("betreff:"):
            data.title = l.split(":", 1)[1].strip()
        elif low.startswith("teilnehmer:"):
            raw = l.split(":", 1)[1].strip()
            data.participants = [p.strip() for p in re.split(r"[,;]", raw) if p.strip()]
        elif low.startswith("entschuldigt:"):
            raw = l.split(":", 1)[1].strip()
            data.absent = [p.strip() for p in re.split(r"[,;]", raw) if p.strip()]
        elif low.startswith("nächstes meeting:") or low.startswith("next meeting:"):
            data.next_meeting = l.split(":", 1)[1].strip()

    # Use raw notes as summary when AI is unavailable
    data.summary = "Automatische Analyse nicht verfügbar – Rohdaten siehe unten."
    data.topics = ["Rohdaten der Meeting-Notizen (AI-Verarbeitung übersprungen)"]
    return data


def process_notes(
    raw_notes: str,
    model_name: str = "Meta-Llama-3-8B-Instruct.Q4_0.gguf",
    skip_ai: bool = False,
    verbose: bool = False,
) -> MeetingData:
    """
    Process raw meeting notes and return structured MeetingData.

    Args:
        raw_notes: Raw text of the meeting notes
        model_name: Name of the local GPT4All model to use
        skip_ai: If True, use regex-based parsing only (no AI)
        verbose: Print progress messages
    """
    if skip_ai or not GPT4ALL_AVAILABLE:
        if verbose:
            reason = "skip_ai=True" if skip_ai else "gpt4all not installed"
            print(f"[AI] Überspringe KI-Verarbeitung ({reason}), nutze Fallback-Parser.")
        return _fallback_parse(raw_notes)

    try:
        if verbose:
            print(f"[AI] Lade Modell: {model_name} ...")
        model = GPT4All(model_name, verbose=False)
        prompt = _build_prompt(raw_notes)

        if verbose:
            print("[AI] Analysiere Notizen ...")
        with model.chat_session():
            response = model.generate(prompt, max_tokens=2048, temp=0.1)

        if verbose:
            print("[AI] Parsing der Antwort ...")
        parsed = _parse_json_from_response(response)

        if not parsed:
            if verbose:
                print("[AI] JSON-Parsing fehlgeschlagen, nutze Fallback-Parser.")
            return _fallback_parse(raw_notes)

        data = MeetingData(
            title=parsed.get("title", "Meeting-Protokoll"),
            date=parsed.get("date", ""),
            time=parsed.get("time", ""),
            location=parsed.get("location", ""),
            participants=parsed.get("participants", []),
            absent=parsed.get("absent", []),
            summary=parsed.get("summary", ""),
            topics=parsed.get("topics", []),
            decisions=parsed.get("decisions", []),
            action_items=[
                ActionItem(
                    task=a.get("task", ""),
                    owner=a.get("owner", ""),
                    due_date=a.get("due_date", ""),
                )
                for a in parsed.get("action_items", [])
                if isinstance(a, dict)
            ],
            next_steps=parsed.get("next_steps", []),
            open_questions=parsed.get("open_questions", []),
            next_meeting=parsed.get("next_meeting", ""),
        )
        return data

    except Exception as e:
        if verbose:
            print(f"[AI] Fehler: {e} – nutze Fallback-Parser.")
        return _fallback_parse(raw_notes)
