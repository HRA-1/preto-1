#!/bin/bash

# Development start script
# Includes both Jupyter Notebook and Streamlit

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Set the PYTHONPATH to include the src directory
export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}/src"

# Enable development mode for faster data loading
export STREAMLIT_DEV_MODE=true

echo "🚀 Starting in DEVELOPMENT mode..."
echo "🔧 STREAMLIT_DEV_MODE=true (50 employees, 2024-current data)"

# Start Jupyter Notebook using the config file
cd "${PROJECT_ROOT}"
echo "📓 Starting Jupyter Notebook on port 8888..."
jupyter notebook --config=jupyter_notebook_config.py &

# Start Streamlit app
echo "🎯 Starting Streamlit app on port 8501..."
streamlit run src/app.py --server.port=8501 --server.address=0.0.0.0