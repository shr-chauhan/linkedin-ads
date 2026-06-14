FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py campaign_report.py metrics_registry.py ./

ENV CAMPAIGNS_FILE=/data/campaigns.json \
    CACHE_DIR=/data/cache \
    TOKEN_FILE=/data/token.json

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
