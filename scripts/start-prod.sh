#!/bin/bash

# Production start script
# Only runs Streamlit (no Jupyter Notebook for security and resource efficiency)

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Set the PYTHONPATH to include the src directory
export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}/src"

# Disable development mode for full dataset
export STREAMLIT_DEV_MODE=false

echo "🚀 Starting in PRODUCTION mode..."
echo "🔧 STREAMLIT_DEV_MODE=false (1000 employees, 2020-current data)"

# Sync markdown files before starting services
echo "🔄 Syncing markdown files..."
if [ -f "${SCRIPT_DIR}/sync-markdown.sh" ]; then
    cd "${PROJECT_ROOT}" && ./scripts/sync-markdown.sh
else
    echo "⚠️  Markdown sync script not found, skipping..."
fi

# Start Streamlit app (production only)
cd "${PROJECT_ROOT}"
echo "🎯 Starting Streamlit app on port 8501..."
echo "📝 Production mode: Jupyter Notebook disabled for security"

# Production-optimized Streamlit settings
streamlit run src/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false