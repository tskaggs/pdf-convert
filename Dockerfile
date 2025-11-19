FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for PyMuPDF
RUN apt-get update && apt-get install -y \
    build-essential \
    libcrypt1 \
    libcrypt-dev \
    libmupdf-dev \
    && ldconfig \
    && (find /usr/lib -name "libcrypt.so.1" -exec sh -c 'ln -sf "$1" "$(dirname "$1")/libcrypt.so.2"' _ {} \; || true) \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY database.py .
COPY auth.py .
COPY seed.py .

# Create startup script that only seeds if database doesn't exist
RUN echo '#!/bin/bash\nmkdir -p /app/data\nif [ ! -f /app/data/pdf_convert.db ]; then\n  python seed.py\nfi\nuvicorn main:app --host 0.0.0.0 --port 8000' > /app/start.sh && \
    chmod +x /app/start.sh

# Expose port
EXPOSE 8000

# Run the application
CMD ["/app/start.sh"]

