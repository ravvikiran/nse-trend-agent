#!/bin/bash
# NSE Trend Scanner - Web UI Launcher
# This script starts both the scanner and the web UI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   NSE Trend Scanner - Web UI Launcher              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo -e "${YELLOW}Please create it first:${NC}"
    echo "   python -m venv .venv"
    echo "   source .venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Check if Flask is installed
if ! python -c "import flask" 2>/dev/null; then
    echo -e "${RED}❌ Flask not installed!${NC}"
    echo -e "${YELLOW}Installing Flask...${NC}"
    pip install flask flask-cors
fi

# Parse command line arguments
MODE=${1:-"ui"}  # Default to UI only
PORT=${2:-5000}

case $MODE in
    "ui")
        echo -e "${GREEN}✓ Starting Web UI + Scanner${NC}"
        echo -e "${YELLOW}Dashboard available at: http://localhost:${PORT}${NC}"
        echo ""
        export PORT
        python src/main.py
        ;;
    
    "both")
        echo -e "${GREEN}✓ Starting Web UI + Scanner (both)${NC}"
        echo -e "${YELLOW}Dashboard available at: http://localhost:${PORT}${NC}"
        echo ""
        export PORT
        python src/main.py
        ;;
    
    "help")
        echo "Usage: ./run_ui.sh [MODE] [PORT]"
        echo ""
        echo "Modes:"
        echo "  ui       - Run Web UI + Scanner together (default)"
        echo "  help     - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./run_ui.sh                    # Run on port 5000"
        echo "  ./run_ui.sh ui 8000            # Run on port 8000"
        echo ""
        echo "Note: This starts both the scanner and web UI in a single process."
        ;;
    
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo "Use 'help' for usage information: ./run_ui.sh help"
        exit 1
        ;;
esac
