# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

# Use eventlet via running the python app
CMD ["python", "app.py"]
