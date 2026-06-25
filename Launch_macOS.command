#!/bin/bash
# Istanbul Route Optimizer — macOS Launcher
# Double-click this file to start the server and open the browser automatically.

# Resolve the real directory of this script (follows symlinks)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================="
echo "   Istanbul Route Optimizer — Starting..."
echo "============================================="
echo ""

# 1. Check virtual environment
# ── Sistem Python'u bul ───────────────────────────────────
SYS_PYTHON=""
if command -v python3 &>/dev/null; then
    SYS_PYTHON="python3"
elif command -v python &>/dev/null; then
    SYS_PYTHON="python"
else
    echo "ERROR: Python bulunamadı!"
    echo "Python 3.10+ adresinden kurun: https://www.python.org"
    echo ""
    echo "Press Enter to close..."
    read
    exit 1
fi

# ── .venv yoksa setup_env.py ile otomatik kur ─────────────
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python3" ] && [ ! -f ".venv/bin/python" ]; then
    echo ""
    echo "Sanal ortam (.venv) bulunamadı."
    echo "Otomatik kurulum başlatılıyor (setup_env.py)..."
    echo "Bu işlem internet bağlantısına göre 5-20 dakika sürebilir."
    echo ""
    "$SYS_PYTHON" setup_env.py
    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: Otomatik kurulum başarısız. Hata mesajlarını inceleyin."
        echo "Press Enter to close..."
        read
        exit 1
    fi
fi

# ── .venv Python binary'ini seç ───────────────────────────
PYTHON_BIN=""
if [ -f ".venv/bin/python3" ]; then
    PYTHON_BIN=".venv/bin/python3"
elif [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
else
    PYTHON_BIN="$SYS_PYTHON"
fi

source .venv/bin/activate 2>/dev/null || true

echo "Python  : $($PYTHON_BIN --version 2>&1)"
echo "Project : $SCRIPT_DIR"
echo ""

# 2. Check data files and download/generate if missing
if [ ! -f "models/checkpoints/best_heuristic_net.pt" ] || \
   [ ! -f "data/processed/full_hierarchy.graphml" ]; then
    echo "Data files not found. Running setup_data.py..."
    echo "(This may take 5-15 minutes on first run)"
    echo ""
    "$PYTHON_BIN" setup_data.py
    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: setup_data.py failed. Check the output above."
        echo "Press Enter to close..."
        read
        exit 1
    fi
fi

# 3. Open browser automatically after 2 seconds
(sleep 2 && open http://127.0.0.1:5001) &

# 4. Start Flask web server
echo "Server starting at: http://127.0.0.1:5001"
echo "Press Ctrl+C to stop."
echo ""
"$PYTHON_BIN" app.py
