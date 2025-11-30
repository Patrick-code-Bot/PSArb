#!/bin/bash
# Quick setup script for PAXG-XAUT Grid Strategy

set -e

echo "================================================================================"
echo "PAXG-XAUT Grid Strategy - Setup Script"
echo "================================================================================"
echo ""

# Check Python version
echo "[1/4] Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if Python version is 3.10 or higher
required_version="3.10"
if ! python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "❌ ERROR: Python 3.10 or higher is required"
    echo "Current version: $python_version"
    exit 1
fi
echo "✅ Python version OK"
echo ""

# Install dependencies
echo "[2/4] Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
echo "[3/4] Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file from template"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and add your Bybit API credentials:"
    echo "   - BYBIT_API_KEY"
    echo "   - BYBIT_API_SECRET"
    echo ""
else
    echo "✅ .env file already exists"
    echo ""
fi

# Create logs directory
echo "[4/4] Creating logs directory..."
mkdir -p logs
echo "✅ Logs directory created"
echo ""

echo "================================================================================"
echo "Setup Complete!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env file and add your Bybit API credentials"
echo "  2. Review configuration in config_live.py"
echo "  3. Run: python run_live.py"
echo ""
echo "For detailed instructions, see README_SETUP.md"
echo "================================================================================"
