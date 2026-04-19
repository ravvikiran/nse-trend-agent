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
        echo -e "${GREEN}✓ Starting Web UI Server${NC}"
        echo -e "${YELLOW}Dashboard will be available at: http://localhost:${PORT}${NC}"
        echo ""
        python src/api.py --port $PORT
        ;;
    
    "both")
        echo -e "${GREEN}✓ Starting Both Scanner and Web UI${NC}"
        echo -e "${YELLOW}Dashboard available at: http://localhost:${PORT}${NC}"
        echo ""
        
        # Note: This is a simplified example
        # For production, use process managers like supervisord or systemd
        echo -e "${BLUE}Starting Scanner...${NC}"
        python src/main.py &
        SCANNER_PID=$!
        
        sleep 2
        
        echo -e "${BLUE}Starting Web UI on port ${PORT}...${NC}"
        python src/api.py --port $PORT
        
        # Cleanup on exit
        trap "kill $SCANNER_PID" EXIT
        ;;
    
    "help")
        echo "Usage: ./run_ui.sh [MODE] [PORT]"
        echo ""
        echo "Modes:"
        echo "  ui       - Run Web UI only (default)"
        echo "  both     - Run Scanner + Web UI together"
        echo "  help     - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./run_ui.sh                    # Run UI on port 5000"
        echo "  ./run_ui.sh ui 8000            # Run UI on port 8000"
        echo "  ./run_ui.sh both 5000          # Run scanner + UI"
        ;;
    
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo "Use 'help' for usage information: ./run_ui.sh help"
        exit 1
        ;;
esac
