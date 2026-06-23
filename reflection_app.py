"""
Selbstreflexions-Chat – lokale Flask-App mit Claude (Anthropic API).
Start: python reflection_app.py
"""

import json
import os
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from threading import Timer

import anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

MEMORY_FILE = Path(__file__).parent / "reflection_memory.json"
CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"

# ── Krisenworte (Deutsch) ──────────────────────────────────────────────────────
CRISIS_PATTERNS = re.compile(
    r"\b(suizid|selbstmord|umbringen|sterben\s+wollen|nicht\s+mehr\s+leben"
    r"|selbstverletz|ritzen|aufh[oö]ren\s+wollen\s+zu\s+leben"
    r"|keinen\s+ausweg|hoffnungslos|niemand\s+braucht\s+mich)\b",
    re.IGNORECASE,
)

CRISIS_HINT = (
    "\n\n---\n**Wichtige Hinweise:**\n"
    "Wenn du dich in einer akuten Krise befindest, bitte ruf sofort an:\n"
    "- **Telefonseelsorge (kostenlos, 24/7):** 0800 111 0 111 oder 0800 111 0 222\n"
    "- **Notruf:** 112\n"
    "- **Krisentelefon für junge Menschen:** 0800 111 0 333\n\n"
    "Du bist nicht allein. Professionelle Hilfe ist da."
)

SYSTEM_PROMPT = """Du bist ein einfühlsamer, nicht wertender Gesprächsbegleiter für Selbstreflexion und persönliches Wachstum.

WICHTIGE EINSCHRÄNKUNGEN:
- Du bist KEIN lizenzierter Therapeut, Psychologe oder Arzt.
- Du ersetzt KEINE professionelle psychologische oder psychiatrische Behandlung.
- Bei ernsthaften psychischen Problemen, Krisen oder Notfällen verweise aktiv auf professionelle Hilfe.

DEINE ROLLE:
- Höre aufmerksam zu und spiegele Gedanken und Gefühle einfühlsam zurück.
- Stelle offene, zum Nachdenken anregende Fragen.
- Hilf dabei, Muster, Stärken und Wachstumsbereiche zu erkennen.
- Bleibe immer respektvoll, geduldig und unterstützend.
- Antworte auf Deutsch, es sei denn, der Nutzer schreibt in einer anderen Sprache.
- Halte Antworten prägnant (3–6 Sätze), sofern keine ausführlichere Antwort sinnvoll ist.

KONTEXT AUS FRÜHEREN GESPRÄCHEN:
{memory_context}
"""


# ── Gedächtnis ─────────────────────────────────────────────────────────────────

def load_memory() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "topics": [],
        "concerns": [],
        "important_people": [],
        "progress": [],
        "raw_summary": "",
        "last_updated": "",
    }


def save_memory(data: dict) -> None:
    data["last_updated"] = datetime.now().isoformat(timespec="minutes")
    MEMORY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def memory_to_context(mem: dict) -> str:
    if not any([mem["topics"], mem["concerns"], mem["important_people"],
                mem["progress"], mem["raw_summary"]]):
        return "Kein vorheriger Kontext vorhanden – dies ist der erste Start."
    parts = []
    if mem["topics"]:
        parts.append("Bisherige Themen: " + ", ".join(mem["topics"]))
    if mem["concerns"]:
        parts.append("Sorgen / Herausforderungen: " + ", ".join(mem["concerns"]))
    if mem["important_people"]:
        parts.append("Wichtige Personen: " + ", ".join(mem["important_people"]))
    if mem["progress"]:
        parts.append("Fortschritte / Erkenntnisse: " + ", ".join(mem["progress"]))
    if mem["raw_summary"]:
        parts.append("Zusammenfassung: " + mem["raw_summary"])
    return "\n".join(parts)


def update_memory_from_conversation(history: list, current_mem: dict) -> dict:
    """Zweiter API-Call: extrahiert wichtige Infos aus dem Gesprächsverlauf."""
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-10:]
    )
    extraction_prompt = f"""Analysiere diesen Gesprächsausschnitt und extrahiere strukturierte Informationen.
Antworte NUR mit einem JSON-Objekt in diesem Format (keine weiteren Texte):
{{
  "topics": ["Liste der besprochenen Hauptthemen"],
  "concerns": ["Sorgen, Herausforderungen, Belastungen"],
  "important_people": ["Namen oder Rollen wichtiger Personen (z.B. 'Mutter', 'Chef Jonas')"],
  "progress": ["Erkenntnisse, Fortschritte, positive Entwicklungen"],
  "raw_summary": "Ein Satz Zusammenfassung des Gesprächskerns"
}}

Gesprächsausschnitt:
{conversation_text}

Aktuell gespeichert (ergänze/merge, nicht ersetzen wenn sinnvoll):
{json.dumps(current_mem, ensure_ascii=False)}
"""
    try:
        resp = CLIENT.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": extraction_prompt}],
        )
        raw = resp.content[0].text.strip()
        # JSON aus dem Antworttext extrahieren
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            extracted = json.loads(json_match.group())
            # Deduplizierte Listen mergen
            for key in ["topics", "concerns", "important_people", "progress"]:
                merged = list(dict.fromkeys(
                    current_mem.get(key, []) + extracted.get(key, [])
                ))
                current_mem[key] = merged[:20]  # max 20 Einträge pro Kategorie
            if extracted.get("raw_summary"):
                current_mem["raw_summary"] = extracted["raw_summary"]
    except Exception:
        pass  # Gedächtnis-Update ist optional, Chat läuft weiter
    return current_mem


# ── Flask-Routen ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "history" not in session:
        session["history"] = []
    memory = load_memory()
    return render_template("chat.html", memory=memory)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Leere Nachricht"}), 400

    if "history" not in session:
        session["history"] = []

    history: list = list(session["history"])
    history.append({"role": "user", "content": user_message})

    memory = load_memory()
    system = SYSTEM_PROMPT.format(memory_context=memory_to_context(memory))

    # Hauptantwort
    response = CLIENT.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=history,
    )
    assistant_text = response.content[0].text

    # Krisencheck
    is_crisis = bool(CRISIS_PATTERNS.search(user_message))
    if is_crisis:
        assistant_text += CRISIS_HINT

    history.append({"role": "assistant", "content": assistant_text})
    session["history"] = history
    session.modified = True

    # Gedächtnis asynchron-ähnlich aktualisieren (im selben Request, aber nach Antwort)
    updated_memory = update_memory_from_conversation(history, memory)
    save_memory(updated_memory)

    return jsonify({
        "reply": assistant_text,
        "crisis": is_crisis,
        "memory_updated": True,
    })


@app.route("/memory", methods=["GET"])
def get_memory():
    return jsonify(load_memory())


@app.route("/memory/clear", methods=["POST"])
def clear_memory():
    empty = {
        "topics": [], "concerns": [], "important_people": [],
        "progress": [], "raw_summary": "", "last_updated": "",
    }
    save_memory(empty)
    return jsonify({"status": "gelöscht"})


@app.route("/history/clear", methods=["POST"])
def clear_history():
    session["history"] = []
    session.modified = True
    return jsonify({"status": "Verlauf gelöscht"})


# ── Start ──────────────────────────────────────────────────────────────────────

def open_browser():
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("FEHLER: ANTHROPIC_API_KEY nicht gesetzt. Bitte .env-Datei anlegen.")
        raise SystemExit(1)
    print("Selbstreflexions-Chat startet auf http://localhost:5000")
    Timer(1.5, open_browser).start()
    app.run(debug=False, port=5000)
