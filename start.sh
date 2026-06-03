#!/usr/bin/env bash
set -e

echo "=== Meeting Notes Processor ==="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "Fehler: Python 3 ist nicht installiert."
  exit 1
fi

# Install deps if needed
if ! python3 -c "import fastapi" &>/dev/null 2>&1; then
  echo "Installiere Abhängigkeiten..."
  pip3 install -r requirements.txt --quiet
fi

# System packages for WeasyPrint (Debian/Ubuntu)
if command -v apt-get &>/dev/null; then
  if ! dpkg -l libpango-1.0-0 &>/dev/null 2>&1; then
    echo "Installiere System-Bibliotheken für PDF-Erstellung..."
    sudo apt-get install -y -q libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev 2>/dev/null || true
  fi
fi

echo ""
echo "  Starte Server auf http://localhost:8000"
echo "  Öffne deinen Browser und gehe zu: http://localhost:8000"
echo ""
echo "  Strg+C zum Beenden"
echo ""

cd "$(dirname "$0")"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
