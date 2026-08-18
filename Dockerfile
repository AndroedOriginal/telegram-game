FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent SQLite file lives here; mount a volume at /app/data on
# platforms that support it so game state survives redeploys.
ENV DATABASE_PATH=/app/data/chess_royale.sqlite3
RUN mkdir -p /app/data

CMD ["python", "main.py"]
