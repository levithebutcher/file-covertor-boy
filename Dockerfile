# ==============================================================================
# PRODUCTION DOCKERFILE FOR RENDER FREE (512MB RAM OPTIMIZED)
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=10000

# Install system dependencies: FFmpeg, 7-Zip, archive tools, and speedup build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    p7zip-full \
    curl \
    ca-certificates \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user for security compliance
RUN useradd -m -u 1000 -s /bin/bash botuser

WORKDIR /app

# Copy dependency definition first for layer caching
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=botuser:botuser . .

# Create required runtime directories and set ownership
RUN mkdir -p /app/temp /app/sessions && \
    chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Expose Render web port
EXPOSE 10000

# Start bot service
CMD ["python", "-m", "bot"]
