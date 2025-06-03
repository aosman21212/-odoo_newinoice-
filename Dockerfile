FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create logs directory
RUN mkdir -p /app/logs

# Copy the application code
COPY run.py .

# Expose the port the app runs on
EXPOSE 8000

# Run the script with uvicorn
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"] 