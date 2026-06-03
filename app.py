"""FastAPI web app for the Meeting Notes Tool."""

import os
from pathlib import Path
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import io

from ai_processor import process_notes, MeetingData, ActionItem
from pdf_generator import generate_pdf

app = FastAPI(title="Meeting Notes Tool")

_HTML = Path(__file__).parent / "templates" / "index.html"


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_HTML.read_text(encoding="utf-8"))


@app.post("/process")
async def process(
    notes: str = Form(...),
    model_name: str = Form("Meta-Llama-3-8B-Instruct.Q4_0.gguf"),
    skip_ai: bool = Form(False),
):
    data = process_notes(notes, model_name=model_name, skip_ai=skip_ai, verbose=True)
    return JSONResponse({
        "title":          data.title,
        "date":           data.date,
        "time":           data.time,
        "location":       data.location,
        "participants":   data.participants,
        "absent":         data.absent,
        "summary":        data.summary,
        "topics":         data.topics,
        "decisions":      data.decisions,
        "action_items":   [
            {"task": a.task, "owner": a.owner, "due_date": a.due_date}
            for a in data.action_items
        ],
        "next_steps":     data.next_steps,
        "open_questions": data.open_questions,
        "next_meeting":   data.next_meeting,
    })


@app.post("/generate-pdf")
async def generate(payload: Request):
    body = await payload.json()
    data = MeetingData(
        title=body.get("title", "Meeting-Protokoll"),
        date=body.get("date", ""),
        time=body.get("time", ""),
        location=body.get("location", ""),
        participants=body.get("participants", []),
        absent=body.get("absent", []),
        summary=body.get("summary", ""),
        topics=body.get("topics", []),
        decisions=body.get("decisions", []),
        action_items=[
            ActionItem(
                task=a.get("task", ""),
                owner=a.get("owner", ""),
                due_date=a.get("due_date", ""),
            )
            for a in body.get("action_items", [])
        ],
        next_steps=body.get("next_steps", []),
        open_questions=body.get("open_questions", []),
        next_meeting=body.get("next_meeting", ""),
    )
    pdf_bytes = generate_pdf(data)
    safe_title = data.title.replace(" ", "_")[:40]
    filename = f"Protokoll_{safe_title}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
