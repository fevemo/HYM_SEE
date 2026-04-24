#!/bin/bash
set -e

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add uv to PATH for the rest of this script
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "uv already installed: $(uv --version)"
fi

# Create virtual environment with Python 3.11
echo "Creating Python 3.11 virtual environment..."
uv venv --python 3.11

# Install dependencies
echo "Installing dependencies..."
uv pip install -r requirements.txt

echo ""
echo "Setup complete! Activate the environment with:"
echo "  source .venv/bin/activate"
