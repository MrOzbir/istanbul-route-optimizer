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
PYTHON_BIN=""

if [ -d ".venv" ]; then
    # Prefer the venv Python directly (works even without source activate)
    if [ -f ".venv/bin/python3" ]; then
        PYTHON_BIN=".venv/bin/python3"
    elif [ -f ".venv/bin/python" ]; then
        PYTHON_BIN=".venv/bin/python"
    fi

    # Also activate so sub-processes inherit the env
    source .venv/bin/activate 2>/dev/null || true
fi

# Fallback: use system python3
if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 &>/dev/null; then
        PYTHON_BIN="python3"
    elif command -v python &>/dev/null; then
        PYTHON_BIN="python"
    else
        echo "ERROR: Python not found!"
        echo "Please install Python 3.10+ from https://www.python.org"
        echo ""
        echo "Press Enter to close..."
        read
        exit 1
    fi
fi

if [ -z "$(ls .venv/bin/ 2>/dev/null)" ]; then
    echo "ERROR: .venv folder not found or empty!"
    echo "Please set up the virtual environment first:"
    echo "  python3 -m venv .venv && source .venv/bin/activate"
    echo "  pip install -r requirements.txt   (or follow README.md)"
    echo ""
    echo "Press Enter to close..."
    read
    exit 1
fi

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
