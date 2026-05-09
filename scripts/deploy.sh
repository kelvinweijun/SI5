#!/bin/bash
# Deployment script for Render.com

set -e

echo "================================"
echo "Agentic AI Bot - Deploy Script"
echo "================================"

# Check Python version
python_version=$(python --version 2>&1)
echo "Python version: $python_version"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating data directories..."
mkdir -p data/chromadb
mkdir -p data/logs
mkdir -p config

# Validate configuration
echo "Validating configuration..."
if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "ERROR: DISCORD_BOT_TOKEN is not set!"
    exit 1
fi

if [ ! -f "$CEREBRAS_API_KEYS_FILE" ] && [ -z "$CEREBRAS_API_KEY" ]; then
    echo "WARNING: No Cerebras API keys found. Bot will not be able to generate responses."
fi

# Run health check
echo "Running health check..."
python -c "import src.main; print('Import successful')"

echo "================================"
echo "Deployment ready!"
echo "================================"
