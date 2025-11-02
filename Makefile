# Preto Project Makefile

.PHONY: install run clean help start

# Default target
help:
	@echo "Available commands:"
	@echo "  install        - Install Python dependencies"
	@echo "  start          - Start all services (Jupyter + Streamlit)"
	@echo "  run            - Run Streamlit app only"
	@echo "  clean          - Remove temp files"
	@echo "  help           - Show this help message"

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

# Start all services (recommended)
start:
	@echo "🚀 Starting all services..."
	./scripts/start.sh

# Run Streamlit app only
run:
	@echo "🚀 Starting Streamlit app only..."
	streamlit run src/app.py

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup completed"