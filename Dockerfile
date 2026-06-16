# VoiceOS Multi-Agent Operating System - Docker Configuration
# Voice + CLI driven AI system with safe system control

FROM python:3.11-slim

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Audio processing dependencies
    portaudio19-dev \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    # System control dependencies
    xvfb \
    x11-utils \
    # Display server for GUI applications
    # File processing
    curl \
    wget \
    git \
    # Text editors
    nano \
    vim \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt chardet

# Additional dependencies for Docker environment
RUN pip install --no-cache-dir \
    # System automation
    pyautogui \
    pygetwindow \
    psutil \
    # File operations
    send2trash \
    # Web scraping
    beautifulsoup4 \
    duckduckgo-search \
    # Data processing
    pandas \
    numpy \
    # Audio processing (if needed)
    sounddevice \
    pyaudio

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/workspace /app/memory /app/logs /app/models /app/config

# Set permissions
RUN chmod +x /app/main.py

# Create non-root user for security
RUN useradd -m -u 1000 voiceos && \
    chown -R voiceos:voiceos /app
USER voiceos

# Create startup script
RUN echo '#!/bin/bash\n\
echo "Starting VoiceOS Multi-Agent System..."\n\
echo "Available commands:"\n\
echo "  python main.py              - Start VoiceOS"\n\
echo "  python main.py --help      - Show help"\n\
echo "  python main.py --status   - Check system status"\n\
echo ""\n\
echo "VoiceOS Features:"\n\
echo "  - Voice interaction (STT → LLM → TTS)"\n\
echo "  - CLI interaction with hybrid mode"\n\
echo "  - Dynamic agent creation"\n\
echo "  - Safe system control"\n\
echo "  - Code development mode"\n\
echo "  - Research and analysis"\n\
echo ""\n\
echo "Starting VoiceOS..."\n\
exec python main.py "$@"' > /app/entrypoint.sh && \
chmod +x /app/entrypoint.sh

# Expose port for potential web interface
EXPOSE 8000

# Health check
RUN echo '#!/bin/bash\n\
python -c "import sys; sys.exit(0)" 2>/dev/null && echo "healthy" || echo "unhealthy"' > /app/healthcheck.sh && \
chmod +x /app/healthcheck.sh
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python main.py --test || exit 1

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["python", "main.py"]

# Labels for metadata
LABEL maintainer="VoiceOS Team"
LABEL version="1.0.0"
LABEL description="VoiceOS Multi-Agent Operating System"
LABEL features="voice,cli,agents,automation,development,research,analysis"
