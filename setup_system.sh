#!/bin/bash

# GPW Trading Advisor - Final Setup Script
# This script prepares your system for first startup

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 GPW Trading Advisor - Final Setup${NC}"
echo "================================================"

# Get project directory
PROJECT_DIR="/Users/bartoszkolek/Desktop/cloud/Projekty/GPW2"

if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Project directory not found: $PROJECT_DIR${NC}"
    exit 1
fi

cd "$PROJECT_DIR"

echo -e "${YELLOW}📁 Setting up directories...${NC}"

# Create necessary directories
mkdir -p logs
mkdir -p run
mkdir -p docs
mkdir -p scripts

echo -e "${YELLOW}🔧 Making scripts executable...${NC}"

# Make all scripts executable
if [ -f "scripts/startup.sh" ]; then
    chmod +x scripts/startup.sh
    echo "✅ startup.sh is executable"
else
    echo -e "${RED}❌ scripts/startup.sh not found${NC}"
    exit 1
fi

if [ -f "scripts/gpw_service.sh" ]; then
    chmod +x scripts/gpw_service.sh
    echo "✅ gpw_service.sh is executable"
else
    echo -e "${RED}❌ scripts/gpw_service.sh not found${NC}"
    exit 1
fi

if [ -f "scripts/gpw_launcher.sh" ]; then
    chmod +x scripts/gpw_launcher.sh
    echo "✅ gpw_launcher.sh is executable"
else
    echo -e "${RED}❌ scripts/gpw_launcher.sh not found${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Checking system requirements...${NC}"

# Check Python virtual environment
if [ -d "venv" ]; then
    echo "✅ Virtual environment found"
else
    echo -e "${YELLOW}⚠️  Virtual environment not found - you may need to create one${NC}"
    echo "   Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
fi

# Check Django project
if [ -f "manage.py" ]; then
    echo "✅ Django project found"
else
    echo -e "${RED}❌ manage.py not found - not a Django project${NC}"
    exit 1
fi

# Check for requirements file
if [ -f "requirements.txt" ]; then
    echo "✅ requirements.txt found"
else
    echo -e "${YELLOW}⚠️  requirements.txt not found${NC}"
fi

echo -e "${YELLOW}🔍 Checking port availability...${NC}"

# Check if port 8000 is available
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${YELLOW}⚠️  Port 8000 is currently in use${NC}"
    echo "   The startup script will handle this automatically"
else
    echo "✅ Port 8000 is available"
fi

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${BLUE}📖 Next Steps:${NC}"
echo "1. Start the system:"
echo "   ${GREEN}./scripts/startup.sh${NC}"
echo ""
echo "2. Or use the service manager:"
echo "   ${GREEN}./scripts/gpw_service.sh start${NC}"
echo ""
echo "3. Or use the GUI launcher:"
echo "   ${GREEN}./scripts/gpw_launcher.sh${NC}"
echo ""
echo "4. Check status:"
echo "   ${GREEN}./scripts/gpw_service.sh status${NC}"
echo ""
echo "5. View dashboard:"
echo "   ${GREEN}open http://127.0.0.1:8000${NC}"
echo ""
echo -e "${BLUE}📚 Documentation:${NC}"
echo "   Complete guide: ${GREEN}docs/STARTUP_SYSTEM_GUIDE.md${NC}"
echo ""
echo -e "${YELLOW}⚡ Quick Start Command:${NC}"
echo "   ${GREEN}./scripts/startup.sh${NC}"

echo ""
echo -e "${GREEN}🎯 System is ready to launch! 🚀${NC}"
