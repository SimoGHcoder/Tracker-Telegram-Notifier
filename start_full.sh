#!/bin/bash

# Change to the directory of this script
cd "$(dirname "$0")"

# Check if the virtual environment exists, and create one if it doesn't
if [ ! -d ".venv" ]; then
    echo "Creating Python Virtual Environment..."
    python3 -m venv .venv
fi

# Activate the Python virtual environment
source .venv/bin/activate

# Upgrade Pip within the virtual environment
echo "Upgrading Pip..."
python3 -m pip install --upgrade pip

# Install/Update dependencies from requirements.txt
echo "Installing/Updating Dependencies..."
pip install -r requirements.txt

# Start the server using Uvicorn
echo "Starting Server at http://localhost:8080 ..."
python3 -m uvicorn app.main:app --reload --port 8080
