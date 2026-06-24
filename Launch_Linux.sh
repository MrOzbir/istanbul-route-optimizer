#!/bin/bash
# Istanbul Route Optimizer — Linux Launcher
# Run this script from the terminal: bash Launch_Linux.sh
# Or make it executable first: chmod +x Launch_Linux.sh && ./Launch_Linux.sh

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
    echo "  pip install osmnx networkx torch onnxruntime onnx flask flask-cors folium"
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
python app.py
