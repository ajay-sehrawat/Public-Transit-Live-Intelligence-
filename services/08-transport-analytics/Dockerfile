FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/08-transport-analytics/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy common libraries and service code
COPY services/common /app/services/common
COPY services/08-transport-analytics /app/services/08-transport-analytics

ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "services/08-transport-analytics/main.py"]
