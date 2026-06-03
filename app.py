import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from weasyprint import HTML

app = FastAPI(title="Meeting Notes Tool")

app.mount("/static", StaticFiles(directory="static"), name="static")

jinja_env = Environment(loader=FileSystemLoader("templates"))

OLLAMA_BASE = "http://localhost:11434"

STRUCTURE_PROMPT = """Du bist ein professioneller Meeting-Assistent. Analysiere die folgenden Meeting-Notizen
und strukturiere sie in ein klares, professionelles Format.

Gib die Antwort AUSSCHLIESSLICH als valides JSON zurück — keine Erklärungen, kein Markdown, kein Codeblock.

JSON-Schema:
{{
  "title": "Meeting-Titel (kurz und prägnant)",
  "date": "Datum im Format DD.MM.YYYY (aus Notizen extrahieren oder '{today}')",
  "time": "Uhrzeit wenn vorhanden, sonst ''",
  "location": "Ort oder 'Remote' wenn online, sonst ''",
  "participants": ["Name 1", "Name 2"],
  "moderator": "Name des Moderators wenn erkennbar, sonst ''",
  "summary": "Executive Summary in 3-4 prägnanten Sätzen",
  "discussion_points": [
    {{"topic": "Thema", "content": "Was wurde diskutiert", "outcome": "Ergebnis oder ''"}}
  ],
  "decisions": ["Getroffene Entscheidung 1", "Entscheidung 2"],
  "action_items": [
    {{"task": "Aufgabe", "responsible": "Verantwortliche Person", "deadline": "Deadline oder 'Offen'"}}
  ],
  "open_issues": ["Offene Frage 1"],
  "next_meeting": "Datum/Zeit des nächsten Meetings wenn erwähnt, sonst ''"
}}

Meeting-Notizen:
{notes}"""


class ProcessRequest(BaseModel):
    notes: str
    model: str = "llama3.2"
    title: str = ""


class PdfRequest(BaseModel):
    data: dict
    logo_text: str = ""


@app.get("/")
async def root():
    return FileResponse("templates/index.html")


@app.get("/api/models")
async def get_models():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return {"models": models, "status": "connected"}
    except Exception:
        return {"models": [], "status": "disconnected"}


@app.post("/api/process")
async def process_notes(req: ProcessRequest):
    if not req.notes.strip():
        raise HTTPException(400, "Meeting-Notizen dürfen nicht leer sein.")

    today = datetime.now().strftime("%d.%m.%Y")
    prompt = STRUCTURE_PROMPT.format(notes=req.notes, today=today)

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                f"{OLLAMA_BASE}/api/generate",
                json={"model": req.model, "prompt": prompt, "stream": False},
            )
    except httpx.ConnectError:
        raise HTTPException(
            503,
            "Ollama ist nicht erreichbar. Bitte starte Ollama mit: ollama serve",
        )
    except httpx.TimeoutException:
        raise HTTPException(504, "Zeitüberschreitung — das Modell hat zu lange gebraucht.")

    raw = r.json().get("response", "")

    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise HTTPException(500, f"KI-Antwort enthielt kein gültiges JSON.\n\nRohantwort:\n{raw[:500]}")

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"JSON-Parse-Fehler: {e}\n\nRohantwort:\n{raw[:500]}")

    if req.title:
        data["title"] = req.title

    return {"success": True, "data": data}


@app.post("/api/generate-pdf")
async def generate_pdf(req: PdfRequest):
    template = jinja_env.get_template("pdf_template.html")
    html_str = template.render(
        meeting=req.data,
        logo_text=req.logo_text or "Meeting Report",
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
    )

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()

    try:
        HTML(string=html_str, base_url=str(Path("templates").resolve())).write_pdf(tmp.name)
    except Exception as e:
        os.unlink(tmp.name)
        raise HTTPException(500, f"PDF-Generierung fehlgeschlagen: {e}")

    title_safe = re.sub(r"[^a-zA-Z0-9_\-äöüÄÖÜ ]", "", req.data.get("title", "meeting"))
    title_safe = title_safe.strip().replace(" ", "_") or "meeting_report"
    filename = f"{title_safe}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return FileResponse(
        tmp.name,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
