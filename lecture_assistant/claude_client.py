"""Wraps Anthropic API calls for summarization and source-grounded Q&A."""

from __future__ import annotations

from anthropic import Anthropic, APIError, AuthenticationError

MODEL = "claude-sonnet-5"


class ClaudeError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _call(api_key: str, system: str, user: str, max_tokens: int) -> str:
    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text.strip()
    except AuthenticationError:
        raise ClaudeError("Ungültiger Anthropic API Key.", 401)
    except APIError as e:
        raise ClaudeError(f"Anthropic-API-Fehler: {e}", 502)


SUMMARY_SYSTEM = (
    "Du bist ein Lern-Assistent, der Vorlesungsmitschriften fuer eine Studentin "
    "oder einen Studenten zusammenfasst. Antworte auf Deutsch, strukturiert in "
    "kurzen Stichpunkten pro Thema. Wenn dir Inhalte aus mehreren Dateien "
    "vorliegen, ordne jeden Stichpunkt eindeutig einer Quelle zu, im Format "
    "'(Quelle: Dateiname)' direkt am Ende der Zeile. Erfinde keine Inhalte, "
    "die nicht im Material stehen."
)

ASK_SYSTEM = (
    "Du beantwortest Fragen AUSSCHLIESSLICH anhand der bereitgestellten "
    "Ausschnitte aus Vorlesungsmitschriften. Belege JEDE Aussage direkt im "
    "Text mit der passenden Quelle im Format '(Quelle: Dateiname, Abschnitt N)'. "
    "Wenn sich die Frage nicht aus den Ausschnitten beantworten laesst, sage "
    "das ausdruecklich und rate nicht."
)


def summarize(api_key: str, sections: list[tuple[str, str]]) -> str:
    body = "\n\n".join(f"[Datei: {name}]\n{text}" for name, text in sections)
    user = f"Fasse folgende Mitschriften zusammen:\n\n{body}"
    return _call(api_key, SUMMARY_SYSTEM, user, max_tokens=2000)


def ask(api_key: str, question: str, context_chunks: list[tuple[str, str]]) -> str:
    body = "\n\n".join(f"[{label}]\n{text}" for label, text in context_chunks)
    user = f"Ausschnitte aus Mitschriften:\n\n{body}\n\nFrage: {question}"
    return _call(api_key, ASK_SYSTEM, user, max_tokens=1200)
