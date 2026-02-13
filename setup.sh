#!/bin/bash

# Quick Setup Script for DeepWiki MCP Server
# This script helps you get started quickly

set -e  # Exit on error

echo "=================================================="
echo "DeepWiki MCP Server - Quick Setup"
echo "=================================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if Python >= 3.9
required_version="3.9"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "❌ Error: Python 3.9 or higher is required"
    exit 1
fi
echo "✅ Python version OK"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate || . .venv/Scripts/activate 2>/dev/null || {
    echo "❌ Failed to activate virtual environment"
    exit 1
}
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --quiet --upgrade pip
echo "✅ pip upgraded"
echo ""

# Install the package
echo "Installing DeepWiki MCP Server..."
pip install --quiet -e .
echo "✅ Package installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created"
    echo "ℹ️  You can customize settings in .env"
else
    echo "ℹ️  .env file already exists"
fi
echo ""

# Test installation
echo "Testing installation..."
if command -v deepwiki-mcp &> /dev/null; then
    echo "✅ deepwiki-mcp command is available"
else
    echo "⚠️  deepwiki-mcp command not found in PATH"
    echo "   You can still run: python -m deepwiki_mcp.server"
fi
echo ""

echo "=================================================="
echo "Setup Complete! 🎉"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. (Optional) Edit .env to customize settings"
echo "2. Run the server:"
echo "   → deepwiki-mcp"
echo "   or"
echo "   → python -m deepwiki_mcp.server"
echo ""
echo "3. Configure Claude Desktop:"
echo "   See INSTALL.md for integration instructions"
echo ""
echo "For more information:"
echo "  - README.md - Full documentation"
echo "  - QUICKSTART.md - Getting started guide"
echo "  - INSTALL.md - Installation options"
echo "  - ARCHITECTURE.md - Technical details"
echo ""
