# Use official lightweight Python image
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Set the working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Environment Variables (Overridden by Cloud Run config)
ENV PORT 8080
ENV SQLITE_DB_PATH /data/game.db


# Create the data directory (for local testing, Cloud Run will mount over this)
RUN mkdir -p /data

# Run the web service on container startup.
# Run the web service on container startup.
# We use Gunicorn with Uvicorn workers for production stability
# Force logging to stdout/stderr so Cloud Run captures it
CMD exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --threads 8 --timeout 0 --access-logfile - --error-logfile - --log-level debug main:app
