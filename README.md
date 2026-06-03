# Meeting Notes Processor

Wandelt rohe Meeting-Notizen mit einer **lokalen KI (Ollama)** in strukturierte PDFs um. Läuft vollständig lokal — keine Daten verlassen deinen Rechner.

## Voraussetzungen

- Python 3.9+
- [Ollama](https://ollama.com) installiert und gestartet
- Ein Ollama-Modell heruntergeladen, z.B.: `ollama pull llama3`

## Starten

```bash
# Einmalig: Abhängigkeiten installieren
pip install -r requirements.txt

# Server starten
./start.sh
# oder direkt:
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Dann im Browser öffnen: **http://localhost:8000**

## Was wird erstellt?

Das PDF enthält:
- **Zusammenfassung** – kurze Übersicht des Meetings
- **Besprochene Themen** – als Tags
- **Entscheidungen** – als Checkliste
- **To-Dos** – Tabelle mit Aufgabe, Verantwortlichem, Termin
- **Offene Fragen**
- **Nächstes Meeting**
- **Originalnotizen** (auf der letzten Seite)

## Struktur

```
Leopold/
├── backend/
│   └── main.py          # FastAPI-Server + Ollama-Integration + PDF-Logik
├── frontend/
│   ├── index.html       # Haupt-UI
│   └── static/
│       ├── css/app.css
│       └── js/app.js
├── templates/
│   └── meeting_pdf.html # PDF-Vorlage (Jinja2)
├── pdfs/                # Generierte PDFs (wird automatisch erstellt)
├── requirements.txt
└── start.sh
```
