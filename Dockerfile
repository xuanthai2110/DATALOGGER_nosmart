FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (build-essential, curl if needed for Modbus/Serial dependencies)
# For pyserial, depending on the arch, GCC might be required, but usually wheel works fine.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tzdata \
    gcc \
    libc-dev \
    && rm -rf /var/lib/apt/lists/*

# Set local timezone (assuming VN timezone for datalogger)
ENV TZ="Asia/Ho_Chi_Minh"

# Copy exactly what is needed for python environment
COPY backend/requirements.txt ./backend/

# Install python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy source code and the env templates
COPY backend/ ./backend/
COPY .env* ./

# Ensure Python output is sent straight to terminal (unbuffered)
ENV PYTHONUNBUFFERED=1

# Default CMD (can be overridden by docker-compose)
CMD ["python", "backend/app.py"]
