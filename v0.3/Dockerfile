FROM python:3.11-slim

WORKDIR /app

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ ./server/
COPY client/dist/ ./client/dist/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "server.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
