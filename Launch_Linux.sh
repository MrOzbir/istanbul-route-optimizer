#!/bin/bash
# Istanbul Route Optimizer — Linux Launcher
# Run this script from the terminal: bash Launch_Linux.sh
# Or make it executable first: chmod +x Launch_Linux.sh && ./Launch_Linux.sh

cd "$(dirname "$0")"

echo "============================================="
echo "   Istanbul Route Optimizer — Starting..."
echo "============================================="

# ── Sistem Python'u bul ───────────────────────────────────
SYS_PYTHON=""
if command -v python3 &>/dev/null; then
    SYS_PYTHON="python3"
elif command -v python &>/dev/null; then
    SYS_PYTHON="python"
else
    echo "ERROR: Python bulunamadı!"
    echo "Sisteminize Python 3.10+ kurun (apt/dnf/snap)."
    echo ""
    read -p "Press Enter to exit..." ; exit 1
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
        echo "ERROR: Otomatik kurulum başarısız."
        read -p "Press Enter to exit..." ; exit 1
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

# 2. Check data files and download/generate if missing
if [ ! -f "models/checkpoints/best_heuristic_net.pt" ] || \
   [ ! -f "data/processed/full_hierarchy.graphml" ]; then
    echo ""
    echo "Data files not found. Running setup_data.py..."
    echo "(This may take 5-15 minutes on first run)"
    echo ""
    "$PYTHON_BIN" setup_data.py
fi

# 3. Detect default browser and open automatically after 2 seconds
open_browser() {
    sleep 2
    if command -v xdg-open &> /dev/null; then
        xdg-open http://127.0.0.1:5001
    elif command -v gnome-open &> /dev/null; then
        gnome-open http://127.0.0.1:5001
    else
        echo "Browser could not be opened automatically."
        echo "Please open manually: http://127.0.0.1:5001"
    fi
}
open_browser &

# 4. Start Flask web server
echo ""
echo "Server starting at: http://127.0.0.1:5001"
echo "Press Ctrl+C to stop."
echo ""
"$PYTHON_BIN" app.py
