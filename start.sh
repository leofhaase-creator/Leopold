#!/usr/bin/env bash
set -e

VENV=".venv"

# Create venv if missing
if [ ! -d "$VENV" ]; then
  echo "→ Erstelle virtuelle Umgebung…"
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

# Install / update deps
echo "→ Installiere Abhängigkeiten…"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo ""
  echo "⚠  Ollama scheint nicht zu laufen."
  echo "   Starte Ollama in einem anderen Terminal: ollama serve"
  echo "   Dann ein Modell laden (falls noch nicht): ollama pull llama3.2"
  echo ""
fi

echo ""
echo "✅ Meeting Notes Tool startet auf http://localhost:8000"
echo "   Stoppen mit Ctrl+C"
echo ""

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
