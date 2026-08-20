# Vorlesungs-Assistent

Ein einfacher, dauerhaft laufender KI-Assistent für deine Vorlesungsmitschriften:

1. **Nimmt Notizen/Transkripte entgegen** – lege `.txt`, `.md` oder `.pdf`-Dateien
   in den Ordner `lecture_assistant/notes/`. Sie werden bei jeder Anfrage neu
   vom Datenträger eingelesen, tauchen also automatisch in der Weboberfläche
   auf, sobald du sie in den Ordner legst – kein Neustart nötig.
2. **Fasst auf Abruf zusammen** – im Tab "Zusammenfassen" wählst du eine
   einzelne Datei oder "Alle Dateien" und bekommst eine strukturierte
   Zusammenfassung.
3. **Beantwortet konkrete Fragen** – im Tab "Frage stellen" durchsucht der
   Assistent alle Mitschriften nach den relevantesten Abschnitten und lässt
   Claude nur anhand dieser Ausschnitte antworten.
4. **Markiert bei jeder Antwort die Quelle** – jede Aussage wird mit
   `(Quelle: Dateiname, Abschnitt N)` versehen, zusätzlich zeigt die Oberfläche
   die tatsächlich durchsuchten Abschnitte als Chips unter jeder Antwort.

Design: schwarz-blaues, reduziertes Single-Page-Interface (keine Frameworks,
nur eine HTML-Datei mit eingebettetem CSS/JS).

## Setup

```bash
cd lecture_assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Öffne danach <http://localhost:5060>.

Du brauchst einen **Anthropic API Key** (aus <https://console.anthropic.com>).
Er wird ausschließlich im Browser (`localStorage`) gespeichert und bei jeder
Anfrage direkt an dein eigenes Backend übergeben, das ihn 1:1 an die
Anthropic-API weiterreicht – er wird nie im Repo oder auf dem Server
persistiert.

## Dateien ablegen

Einfach in `lecture_assistant/notes/` kopieren:

```
lecture_assistant/notes/2026-04-15_Neuronale_Netze.txt
lecture_assistant/notes/2026-04-22_Backprop.md
lecture_assistant/notes/2026-04-29_Skript.pdf
```

PDF-Unterstützung braucht `pypdf` (steht in `requirements.txt`); ist es nicht
installiert, werden PDFs stillschweigend übersprungen und die Oberfläche
zeigt keinen PDF-Hinweis an.

## Dauerhaft laufen lassen

Für den lokalen Alltag reicht es, den Server einfach offen zu lassen (z. B.
in einem `tmux`/`screen`-Fenster oder als Hintergrundprozess mit `nohup`).

Für einen permanent erreichbaren Server (z. B. auf einem eigenen Rechner oder
kleinen Cloud-Server) liegt ein `Dockerfile` bei:

```bash
docker build -t vorlesungs-assistent .
docker run -p 5060:5060 -v $(pwd)/notes:/app/notes vorlesungs-assistent
```

Der `-v`-Mount sorgt dafür, dass Dateien, die du lokal in `notes/` ablegst,
auch im laufenden Container sichtbar sind.

## Architektur (kurz)

- `app.py` – Flask-Routen (`/api/notes`, `/api/summarize`, `/api/ask`)
- `file_store.py` – liest den `notes/`-Ordner ein (txt/md/pdf)
- `retrieval.py` – zerlegt Dateien in Abschnitte und findet per
  Keyword-Scoring die relevantesten Abschnitte zu einer Frage (kein
  Embedding-/Vektor-DB-Dienst nötig)
- `claude_client.py` – ruft die Anthropic API für Zusammenfassung und Q&A auf
  und erzwingt per System-Prompt Quellenangaben
- `templates/index.html` – schwarz-blaues Single-Page-Frontend
