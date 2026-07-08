"""Flask web app: Transkript-Zusammenfasser mit Claude."""

import json
import re

from anthropic import Anthropic, APIError, AuthenticationError
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

MODEL = "claude-sonnet-5"

SUMMARY_PROMPT = (
    "Fasse das folgende Transkript in 5 bis 10 Sätzen auf Deutsch zusammen. "
    "Gib nur die Zusammenfassung zurück, ohne Einleitung oder Kommentare.\n\n"
    "Transkript:\n{transcript}"
)

ASK_SYSTEM_PROMPT = (
    "Du beantwortest Fragen ausschließlich anhand des gegebenen Transkripts. "
    "Antworte NUR mit einem JSON-Objekt in genau diesem Format, ohne Markdown-"
    "Codeblock und ohne weitere Erklärungen:\n"
    '{"answer": "<Antwort in 1-3 Sätzen>", '
    '"quote": "<die exakte Textstelle aus dem Transkript, wortwörtlich kopiert, '
    'die die Antwort belegt>"}\n'
    "Wenn sich die Frage nicht aus dem Transkript beantworten lässt, beantworte "
    "sie so gut wie möglich und setze \"quote\" auf einen leeren String."
)


def _extract_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _find_quote(transcript: str, quote: str) -> bool:
    if not quote:
        return False
    return _normalize(quote) in _normalize(transcript)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/summarize", methods=["POST"])
def summarize():
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    transcript = (data.get("transcript") or "").strip()

    if not api_key:
        return jsonify({"error": "Bitte gib deinen Anthropic API Key ein."}), 400
    if not transcript:
        return jsonify({"error": "Bitte füge ein Transkript ein."}), 400

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": SUMMARY_PROMPT.format(transcript=transcript)}
            ],
        )
        summary = message.content[0].text.strip()
        return jsonify({"summary": summary})
    except AuthenticationError:
        return jsonify({"error": "Ungültiger API Key."}), 401
    except APIError as e:
        return jsonify({"error": f"Anthropic-API-Fehler: {e}"}), 502


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    transcript = (data.get("transcript") or "").strip()
    question = (data.get("question") or "").strip()

    if not api_key:
        return jsonify({"error": "Bitte gib deinen Anthropic API Key ein."}), 400
    if not transcript:
        return jsonify({"error": "Bitte füge ein Transkript ein."}), 400
    if not question:
        return jsonify({"error": "Bitte gib eine Frage ein."}), 400

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=ASK_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Transkript:\n{transcript}\n\nFrage: {question}",
                }
            ],
        )
        raw = message.content[0].text
        parsed = _extract_json(raw)

        answer = parsed.get("answer", "").strip() if parsed else raw.strip()
        quote = parsed.get("quote", "").strip() if parsed else ""
        found = _find_quote(transcript, quote)

        return jsonify({"answer": answer, "quote": quote if found else "", "found": found})
    except AuthenticationError:
        return jsonify({"error": "Ungültiger API Key."}), 401
    except APIError as e:
        return jsonify({"error": f"Anthropic-API-Fehler: {e}"}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
