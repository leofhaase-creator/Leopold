import os
import json
import httpx
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional

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
    language: Optional[str] = "de"
    # AI provider
    provider: Optional[str] = "ollama"   # "ollama" | "groq" | "openai" | "anthropic"
    api_key: Optional[str] = ""
    api_model: Optional[str] = ""
    # Ollama-specific
    ollama_url: Optional[str] = "http://localhost:11434"
    ollama_model: Optional[str] = "llama3"


class CheckRequest(BaseModel):
    provider: str = "ollama"
    ollama_url: Optional[str] = "http://localhost:11434"
    api_key: Optional[str] = ""


PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-haiku-4-5-20251001",
        "models": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-8"],
    },
}

SYSTEM_PROMPT_DE = """Du bist ein professioneller Meeting-Assistent. Analysiere die folgenden Meeting-Notizen und erstelle eine strukturierte Zusammenfassung auf Deutsch.

Gib deine Antwort als valides JSON zurück mit genau dieser Struktur:
{
  "summary": "Kurze Zusammenfassung des Meetings (2-4 Sätze)",
  "key_topics": ["Thema 1", "Thema 2"],
  "decisions": ["Entscheidung 1", "Entscheidung 2"],
  "action_items": [
    {"task": "Aufgabe 1", "responsible": "Person oder Team", "deadline": "Datum oder 'offen'"}
  ],
  "open_questions": ["Offene Frage 1"],
  "next_meeting": "Nächster Termin oder 'nicht besprochen'"
}
Extrahiere nur tatsächlich vorhandene Informationen. Erfinde nichts."""

SYSTEM_PROMPT_EN = """You are a professional meeting assistant. Analyze the following meeting notes and create a structured summary in English.

Return valid JSON with exactly this structure:
{
  "summary": "Brief summary (2-4 sentences)",
  "key_topics": ["Topic 1", "Topic 2"],
  "decisions": ["Decision 1"],
  "action_items": [
    {"task": "Task 1", "responsible": "Person or team", "deadline": "Date or 'open'"}
  ],
  "open_questions": ["Question 1"],
  "next_meeting": "Next meeting date or 'not discussed'"
}
Only extract information actually present in the notes."""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=(FRONTEND_DIR / "index.html").read_text(encoding="utf-8"))


@app.post("/api/check")
async def check_connection(req: CheckRequest):
    if req.provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{req.ollama_url}/api/tags")
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
                    return {"status": "online", "models": models}
        except Exception:
            pass
        return {"status": "offline", "models": []}

    if req.provider in PROVIDERS:
        if not req.api_key:
            return {"status": "no_key"}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                if req.provider == "anthropic":
                    resp = await client.get(
                        "https://api.anthropic.com/v1/models",
                        headers={"x-api-key": req.api_key, "anthropic-version": "2023-06-01"},
                    )
                else:
                    resp = await client.get(
                        f"{PROVIDERS[req.provider]['base_url']}/models",
                        headers={"Authorization": f"Bearer {req.api_key}"},
                    )
            if resp.status_code == 200:
                return {"status": "online", "models": PROVIDERS[req.provider]["models"]}
            return {"status": "invalid_key"}
        except Exception:
            return {"status": "offline"}

    return {"status": "unknown_provider"}


@app.post("/api/process")
async def process_notes(req: ProcessRequest):
    system_prompt = SYSTEM_PROMPT_DE if req.language == "de" else SYSTEM_PROMPT_EN
    user_message = f"MEETING NOTIZEN:\n{req.raw_notes}"

    structured = await call_ai(req, system_prompt, user_message)

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


async def call_ai(req: ProcessRequest, system_prompt: str, user_message: str) -> dict:
    if req.provider == "ollama":
        return await call_ollama(req, system_prompt, user_message)
    elif req.provider == "anthropic":
        return await call_anthropic(req, system_prompt, user_message)
    elif req.provider in ("groq", "openai"):
        return await call_openai_compat(req, system_prompt, user_message)
    else:
        raise HTTPException(status_code=400, detail=f"Unbekannter Provider: {req.provider}")


async def call_ollama(req: ProcessRequest, system_prompt: str, user_message: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{req.ollama_url}/api/generate",
                json={
                    "model": req.ollama_model,
                    "prompt": f"{system_prompt}\n\n---\n{user_message}\n---",
                    "stream": False,
                    "format": "json",
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Ollama Fehler: {resp.text}")
            return parse_json_response(resp.json().get("response", "{}"))
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama nicht erreichbar. Bitte stelle sicher, dass Ollama läuft.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout: Ollama braucht zu lange. Versuche ein kleineres Modell.")


async def call_openai_compat(req: ProcessRequest, system_prompt: str, user_message: str) -> dict:
    provider_cfg = PROVIDERS[req.provider]
    model = req.api_model or provider_cfg["default_model"]
    api_key = req.api_key or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        raise HTTPException(status_code=401, detail=f"Kein API-Key für {req.provider} angegeben.")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{provider_cfg['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Ungültiger API-Key.")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"API Fehler ({resp.status_code}): {resp.text[:300]}")
            return parse_json_response(resp.json()["choices"][0]["message"]["content"])
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout bei der API-Anfrage.")


async def call_anthropic(req: ProcessRequest, system_prompt: str, user_message: str) -> dict:
    api_key = req.api_key or os.getenv("ANTHROPIC_API_KEY", "")
    model = req.api_model or PROVIDERS["anthropic"]["default_model"]

    if not api_key:
        raise HTTPException(status_code=401, detail="Kein Anthropic API-Key angegeben.")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 2048,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Ungültiger Anthropic API-Key.")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Anthropic Fehler: {resp.text[:300]}")
            return parse_json_response(resp.json()["content"][0]["text"])
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout bei Anthropic API.")


def parse_json_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise HTTPException(status_code=500, detail="KI-Antwort konnte nicht als JSON geparst werden.")


async def generate_pdf(structured, title, date, participants, raw_notes, language) -> str:
    from weasyprint import HTML
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
    template = env.get_template("meeting_pdf.html")

    labels_de = {
        "summary_title": "Zusammenfassung", "topics_title": "Besprochene Themen",
        "decisions_title": "Entscheidungen", "actions_title": "To-Dos & Maßnahmen",
        "task_col": "Aufgabe", "responsible_col": "Verantwortlich", "deadline_col": "Termin",
        "questions_title": "Offene Fragen", "next_meeting_title": "Nächstes Meeting",
        "participants_label": "Teilnehmer", "date_label": "Datum",
        "generated_label": "Erstellt am", "raw_notes_title": "Originalnotizen",
    }
    labels_en = {
        "summary_title": "Summary", "topics_title": "Key Topics",
        "decisions_title": "Decisions", "actions_title": "Action Items",
        "task_col": "Task", "responsible_col": "Responsible", "deadline_col": "Deadline",
        "questions_title": "Open Questions", "next_meeting_title": "Next Meeting",
        "participants_label": "Participants", "date_label": "Date",
        "generated_label": "Generated on", "raw_notes_title": "Original Notes",
    }

    html_content = template.render(
        title=title,
        date=date,
        participants=participants,
        generated=datetime.now().strftime("%d.%m.%Y %H:%M"),
        structured=structured,
        raw_notes=raw_notes,
        labels=labels_de if language == "de" else labels_en,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:30].strip().replace(" ", "_")
    filename = f"meeting_{safe_title}_{timestamp}.pdf"
    HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf(str(PDFS_DIR / filename))
    return filename
