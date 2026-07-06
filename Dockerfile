FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MCP_TRANSPORT=http

# Railway/Render inject PORT automatically; default to 8000 for local testing.
ENV PORT=8000
EXPOSE 8000

CMD ["python3", "server.py"]
