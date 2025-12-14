# Base image from python
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set default to development mode (faster startup for development)
# Override with STREAMLIT_DEV_MODE=false for production
ENV STREAMLIT_DEV_MODE=true

# ps -ef 명령어 사용을 위한 의존성 설치
RUN apt-get update && apt-get install -y procps && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies (interpret without optional deps to avoid aplr build failure on ARM64)
RUN grep -v "^interpret" requirements.txt > /tmp/requirements-base.txt && \
    pip install --no-cache-dir -r /tmp/requirements-base.txt && \
    pip install --no-cache-dir interpret --no-deps

# Copy the rest of the application
COPY . .

# Copy Jupyter configuration
COPY jupyter_notebook_config.py /root/.jupyter/

# Expose streamlit and jupyter ports
EXPOSE 8501 8888

# Make scripts executable
RUN chmod +x scripts/start.sh scripts/start-dev.sh scripts/start-prod.sh

# Command to run the app
CMD ["./scripts/start.sh"]
