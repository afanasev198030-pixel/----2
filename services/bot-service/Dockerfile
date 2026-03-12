FROM python:3.11-alpine

WORKDIR /app

# Install system dependencies
RUN apk add --no-cache build-base

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app /app/app

# Run the bot
CMD ["python", "-m", "app.main"]
