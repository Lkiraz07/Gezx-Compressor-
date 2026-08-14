hereFROM python:3.11-slim

# Install system dependencies & FFmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    catdoc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications first to leverage caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose Render Default Port
EXPOSE 8080

# Run Bot Application Engine
CMD ["python", "bot.py"]
