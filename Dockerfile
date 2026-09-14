FROM python:3.11-slim

# Install system dependencies: FFmpeg and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create downloads directories
RUN mkdir -p /app/downloads/temp /app/downloads/pc

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PC_DOWNLOAD_DIR=/app/downloads/pc

# Start Telegram Bot
CMD ["python", "bot.py"]
