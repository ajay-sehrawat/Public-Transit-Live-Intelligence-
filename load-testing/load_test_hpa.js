// ==============================================================================
// S11 Public Transportation System: k6 Sustained Load Testing Suite (Requirement c)
// Target: Service 2 (GPS Ingestion Service) & HPA Scale-Out Validation
// ==============================================================================

import http from 'k6/http';
import { sleep } from 'k6';

// ------------------------------------------------------------------------------
// Load Test Stages: Sustained High-Throughput Telemetry Ingestion Traffic
// 40 concurrent VUs sending JSON payloads triggers real Python CPU execution
// (Pydantic validation, serialization) driving pod CPU > 50% to force HPA scale-out.
// ------------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '15s', target: 30 },  // Quick ramp-up: 30 VUs
    { duration: '2m',  target: 50 },  // Sustained peak: 50 VUs (drives CPU to 70-90% > 50% target)
    { duration: '15s', target: 0 },   // Cool-down to 0 VUs
  ],
};

const BASE_URL = __ENV.INGESTION_URL || 'http://localhost:8002';
const BUS_FLEET = ['BUS-101', 'BUS-102', 'BUS-103', 'BUS-201', 'BUS-202', 'BUS-401'];

export default function () {
  const busId = BUS_FLEET[Math.floor(Math.random() * BUS_FLEET.length)];
  const lat = 28.3600 + (Math.random() - 0.5) * 0.02;
  const lon = 75.5900 + (Math.random() - 0.5) * 0.02;
  const speed = 25.0 + Math.random() * 20.0;
  const heading = Math.random() * 360.0;
  const nowIso = new Date().toISOString();

  // Telemetry POST payload consumes real Python CPU (JSON decoding + Pydantic validation)
  const payload = JSON.stringify({
    bus_id: busId,
    latitude: parseFloat(lat.toFixed(6)),
    longitude: parseFloat(lon.toFixed(6)),
    speed_kmh: parseFloat(speed.toFixed(1)),
    heading: parseFloat(heading.toFixed(1)),
    timestamp: nowIso
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Connection': 'keep-alive',
      'X-Load-Test': 'k6-hpa-benchmark'
    },
    timeout: '3s'
  };

  // Send POST telemetry ping to drive pod CPU
  http.post(`${BASE_URL}/api/v1/telemetry`, payload, params);

  // Also hit health check
  http.get(`${BASE_URL}/health`, {
    headers: { 'Connection': 'keep-alive' },
    timeout: '3s'
  });

  sleep(0.01);
}
