#!/bin/bash
# Istanbul Route Optimizer — macOS Launcher
# Double-click this file to start the server and open the browser automatically.

cd "$(dirname "$0")"

echo "============================================="
echo "   Istanbul Route Optimizer — Starting..."
echo "============================================="

# 1. Check virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo ""
    echo "ERROR: .venv folder not found!"
    echo "Please set up the virtual environment first:"
    echo "  python3 -m venv .venv && source .venv/bin/activate"
    echo "  pip install -r requirements.txt   (or follow README.md)"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# 2. Check data files and download/generate if missing
if [ ! -f "models/checkpoints/best_heuristic_net.pt" ] || \
   [ ! -f "data/processed/full_hierarchy.graphml" ]; then
    echo ""
    echo "Data files not found. Running setup_data.py..."
    echo "(This may take 5-15 minutes on first run)"
    echo ""
    python setup_data.py
fi

# 3. Open browser automatically after 1.5 seconds
(sleep 1.5 && open http://127.0.0.1:5001) &

# 4. Start Flask web server
echo ""
echo "Server starting at: http://127.0.0.1:5001"
echo "Press Ctrl+C to stop."
echo ""
python app.py
