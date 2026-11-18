# Multi-stage Dockerfile for Service 6: Passenger Demand Service
FROM python:3.11-slim as builder

WORKDIR /app
COPY services/06-passenger-demand/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app

RUN addgroup --system appgroup && adduser --system --group appuser

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

COPY services/common /app/services/common
COPY services/06-passenger-demand /app/

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8006

HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8006/health')"

CMD ["python", "main.py"]

