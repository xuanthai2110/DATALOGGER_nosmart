# ---------- Builder ----------
FROM python:3.11-slim AS builder
WORKDIR /app

# Copy only the requirements file and install Python deps (cached)
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the source code
COPY . .

# ---------- Runtime ----------
FROM python:3.11-slim AS runtime
WORKDIR /app

# Set timezone and unbuffered output (không cần cài tzdata qua apt)
ENV TZ="Asia/Ho_Chi_Minh"
ENV PYTHONUNBUFFERED=1

# Copy the built artefacts from the builder stage
COPY --from=builder /app /app
# Sao chép các gói Python đã cài vào runtime
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Default command (can be overridden by docker‑compose)
CMD ["python", "backend/app.py"]