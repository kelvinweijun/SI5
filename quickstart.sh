#!/bin/bash
# Quick Start Script for Local Development

echo "=========================================="
echo "Agentic AI Bot - Quick Start"
echo "=========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env from example..."
    cp .env.example .env
    echo "Please edit .env with your credentials before running."
    exit 1
fi

# Check for API keys
if [ ! -f config/cerebras_api_keys.txt ]; then
    echo "WARNING: config/cerebras_api_keys.txt not found!"
    echo "Create it with your Cerebras API keys (one per line)."
fi

# Check for Discord token
if ! grep -q "DISCORD_BOT_TOKEN=your" .env; then
    echo "Discord token found in .env ✓"
else
    echo "WARNING: DISCORD_BOT_TOKEN not configured in .env"
fi

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Creating data directories..."
mkdir -p data/chromadb data/logs config

echo "=========================================="
echo "Setup complete! Starting bot..."
echo "=========================================="

python -m src.main
