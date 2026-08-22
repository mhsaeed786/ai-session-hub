#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "=== AI Session Hub Setup ==="
echo

# 1. Create virtual environment
if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv venv
else
    echo "[1/3] Virtual environment already exists."
fi

# 2. Install dependencies
echo "[2/3] Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt --quiet

# 3. Optional cron sync (macOS/Linux)
echo "[3/3] Adding daily sync to crontab..."
CRON_LINE="0 2 * * * cd $(pwd) && ./venv/bin/python run.py --sync"
( crontab -l 2>/dev/null | grep -v "ai-session-hub/run.py" ; echo "$CRON_LINE" ) | crontab - || \
    echo "WARNING: could not update crontab."

echo
echo "=== Setup Complete ==="
echo "To sync now:     ./venv/bin/python run.py --sync"
echo "To start server: ./venv/bin/python run.py --serve"
echo "Then open:       http://127.0.0.1:5100"
