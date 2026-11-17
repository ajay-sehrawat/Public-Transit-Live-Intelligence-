# Multi-stage Dockerfile for Service 1: Vehicle Registry
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app

# Security: Run as non-root user inside container
RUN addgroup --system appgroup && adduser --system --group appuser

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

COPY services/common /app/services/common
COPY services/01-vehicle-registry /app/

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8001 50051

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"

CMD ["python", "main.py"]

