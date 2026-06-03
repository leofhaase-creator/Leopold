import os
import json
import httpx
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import subprocess

app = FastAPI(title="Meeting Notes Processor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent.parent
PDFS_DIR = BASE_DIR / "pdfs"
PDFS_DIR.mkdir(exist_ok=True)

FRONTEND_DIR = BASE_DIR / "frontend"

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
app.mount("/pdfs", StaticFiles(directory=str(PDFS_DIR)), name="pdfs")


class ProcessRequest(BaseModel):
    raw_notes: str
    meeting_title: Optional[str] = "Meeting"
    meeting_date: Optional[str] = None
    participants: Optional[str] = ""
    ollama_model: Optional[str] = "llama3"
    ollama_url: Optional[str] = "http://localhost:11434"
    language: Optional[str] = "de"


class OllamaStatus(BaseModel):
    ollama_url: str = "http://localhost:11434"


SYSTEM_PROMPT_DE = """Du bist ein professioneller Meeting-Assistent. Analysiere die folgenden Meeting-Notizen und erstelle eine strukturierte Zusammenfassung auf Deutsch.

Gib deine Antwort als valides JSON zurück mit genau dieser Struktur:
{
  "summary": "Kurze Zusammenfassung des Meetings (2-4 Sätze)",
  "key_topics": ["Thema 1", "Thema 2", "Thema 3"],
  "decisions": ["Entscheidung 1", "Entscheidung 2"],
  "action_items": [
    {"task": "Aufgabe 1", "responsible": "Person oder Team", "deadline": "Datum oder 'offen'"},
    {"task": "Aufgabe 2", "responsible": "Person oder Team", "deadline": "Datum oder 'offen'"}
  ],
  "open_questions": ["Offene Frage 1", "Offene Frage 2"],
  "next_meeting": "Nächster Termin oder 'nicht besprochen'"
}

Extrahiere nur Informationen, die tatsächlich in den Notizen vorhanden sind. Erfinde nichts."""

SYSTEM_PROMPT_EN = """You are a professional meeting assistant. Analyze the following meeting notes and create a structured summary in English.

Return your answer as valid JSON with exactly this structure:
{
  "summary": "Brief summary of the meeting (2-4 sentences)",
  "key_topics": ["Topic 1", "Topic 2", "Topic 3"],
  "decisions": ["Decision 1", "Decision 2"],
  "action_items": [
    {"task": "Task 1", "responsible": "Person or team", "deadline": "Date or 'open'"},
    {"task": "Task 2", "responsible": "Person or team", "deadline": "Date or 'open'"}
  ],
  "open_questions": ["Open question 1", "Open question 2"],
  "next_meeting": "Next meeting date or 'not discussed'"
}

Only extract information actually present in the notes. Do not invent anything."""


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/check-ollama")
async def check_ollama(req: OllamaStatus):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{req.ollama_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"status": "online", "models": models}
    except Exception:
        pass
    return {"status": "offline", "models": []}


@app.post("/api/process")
async def process_notes(req: ProcessRequest):
    system_prompt = SYSTEM_PROMPT_DE if req.language == "de" else SYSTEM_PROMPT_EN

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{req.ollama_url}/api/generate",
                json={
                    "model": req.ollama_model,
                    "prompt": f"{system_prompt}\n\n---\nMEETING NOTIZEN:\n{req.raw_notes}\n---",
                    "stream": False,
                    "format": "json",
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Ollama error: {resp.text}")

            result = resp.json()
            ai_text = result.get("response", "{}")

            try:
                structured = json.loads(ai_text)
            except json.JSONDecodeError:
                import re
                match = re.search(r"\{.*\}", ai_text, re.DOTALL)
                if match:
                    structured = json.loads(match.group())
                else:
                    raise HTTPException(status_code=500, detail="KI-Antwort konnte nicht geparst werden")

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama nicht erreichbar. Bitte stelle sicher, dass Ollama läuft.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout: Die KI braucht zu lange. Bitte versuche ein kleineres Modell.")

    meeting_date = req.meeting_date or datetime.now().strftime("%d.%m.%Y")
    pdf_filename = await generate_pdf(
        structured=structured,
        title=req.meeting_title,
        date=meeting_date,
        participants=req.participants,
        raw_notes=req.raw_notes,
        language=req.language,
    )

    return {
        "structured": structured,
        "pdf_url": f"/pdfs/{pdf_filename}",
        "pdf_filename": pdf_filename,
    }


async def generate_pdf(structured: dict, title: str, date: str, participants: str, raw_notes: str, language: str) -> str:
    from weasyprint import HTML, CSS
    from jinja2 import Environment, FileSystemLoader

    templates_dir = BASE_DIR / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("meeting_pdf.html")

    labels_de = {
        "summary_title": "Zusammenfassung",
        "topics_title": "Besprochene Themen",
        "decisions_title": "Entscheidungen",
        "actions_title": "To-Dos & Maßnahmen",
        "task_col": "Aufgabe",
        "responsible_col": "Verantwortlich",
        "deadline_col": "Termin",
        "questions_title": "Offene Fragen",
        "next_meeting_title": "Nächstes Meeting",
        "participants_label": "Teilnehmer",
        "date_label": "Datum",
        "generated_label": "Erstellt am",
        "raw_notes_title": "Originalnotizen",
    }
    labels_en = {
        "summary_title": "Summary",
        "topics_title": "Key Topics",
        "decisions_title": "Decisions",
        "actions_title": "Action Items",
        "task_col": "Task",
        "responsible_col": "Responsible",
        "deadline_col": "Deadline",
        "questions_title": "Open Questions",
        "next_meeting_title": "Next Meeting",
        "participants_label": "Participants",
        "date_label": "Date",
        "generated_label": "Generated on",
        "raw_notes_title": "Original Notes",
    }
    labels = labels_de if language == "de" else labels_en

    html_content = template.render(
        title=title,
        date=date,
        participants=participants,
        generated=datetime.now().strftime("%d.%m.%Y %H:%M"),
        structured=structured,
        raw_notes=raw_notes,
        labels=labels,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:30].strip().replace(" ", "_")
    filename = f"meeting_{safe_title}_{timestamp}.pdf"
    output_path = PDFS_DIR / filename

    HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf(str(output_path))

    return filename
