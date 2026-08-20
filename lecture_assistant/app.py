"""Flask app: dauerhafter KI-Lern-Assistent fuer Vorlesungsmitschriften
mit On-Demand-Zusammenfassung, Q&A und Quellenangabe je Antwort."""

from pathlib import Path

from flask import Flask, jsonify, render_template, request

import claude_client
from file_store import PDF_SUPPORT, load_notes
from retrieval import build_index, search

app = Flask(__name__)

MAX_SUMMARY_CHARS = 60_000


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/notes")
def api_notes():
    notes = load_notes()
    return jsonify({
        "pdf_support": PDF_SUPPORT,
        "notes": [
            {"name": n.name, "chars": len(n.text), "modified": n.modified}
            for n in notes
        ],
    })


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    target = (data.get("file") or "all").strip()

    if not api_key:
        return jsonify({"error": "Bitte gib deinen Anthropic API Key ein."}), 400

    notes = load_notes()
    if not notes:
        return jsonify({"error": "Keine Mitschriften im notes/-Ordner gefunden."}), 404

    if target != "all":
        notes = [n for n in notes if n.name == target]
        if not notes:
            return jsonify({"error": f"Datei '{target}' nicht gefunden."}), 404

    sections = []
    used_chars = 0
    truncated = False
    for n in notes:
        remaining = MAX_SUMMARY_CHARS - used_chars
        if remaining <= 0:
            truncated = True
            break
        text = n.text[:remaining]
        if len(text) < len(n.text):
            truncated = True
        sections.append((n.name, text))
        used_chars += len(text)

    try:
        summary = claude_client.summarize(api_key, sections)
    except claude_client.ClaudeError as e:
        return jsonify({"error": str(e)}), e.status

    return jsonify({
        "summary": summary,
        "sources": [n.name for n in notes],
        "truncated": truncated,
    })


@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    question = (data.get("question") or "").strip()

    if not api_key:
        return jsonify({"error": "Bitte gib deinen Anthropic API Key ein."}), 400
    if not question:
        return jsonify({"error": "Bitte gib eine Frage ein."}), 400

    notes = load_notes()
    if not notes:
        return jsonify({"error": "Keine Mitschriften im notes/-Ordner gefunden."}), 404

    chunks = build_index(notes)
    top_chunks = search(chunks, question, top_k=6)
    context = [(c.label, c.text) for c in top_chunks]

    try:
        answer = claude_client.ask(api_key, question, context)
    except claude_client.ClaudeError as e:
        return jsonify({"error": str(e)}), e.status

    return jsonify({
        "answer": answer,
        "sources": [c.label for c in top_chunks],
    })


if __name__ == "__main__":
    Path(__file__).parent.joinpath("notes").mkdir(exist_ok=True)
    app.run(host="0.0.0.0", port=5060, debug=True)
