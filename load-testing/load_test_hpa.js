// ==============================================================================
// S11 Public Transportation System: k6 Sustained Load Testing Suite (Requirement c)
// Target: Service 2 (GPS Ingestion Service) & HPA Scale-Out Validation
// Target Endpoint: GCE Public Ingress http://8.233.33.106/api/v1/telemetry
// ==============================================================================

import http from 'k6/http';
import { sleep } from 'k6';

// ------------------------------------------------------------------------------
// Sustained High-Throughput Ingestion Traffic:
// Hits Google Cloud Ingress directly (no port-forward bottleneck) to drive
// pod CPU above the 50% target threshold and trigger live HPA scale-out.
// ------------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '15s', target: 30 },  // Quick ramp-up: 30 VUs
    { duration: '2m',  target: 60 },  // Sustained peak: 60 VUs (~250-400 req/s)
    { duration: '15s', target: 0 },   // Cool-down to 0 VUs
  ],
};

const BASE_URL = __ENV.INGESTION_URL || 'http://8.233.33.106';
const BUS_FLEET = ['BUS-101', 'BUS-102', 'BUS-103', 'BUS-201', 'BUS-202', 'BUS-401'];

export default function () {
  const busId = BUS_FLEET[Math.floor(Math.random() * BUS_FLEET.length)];
  const lat = 28.3600 + (Math.random() - 0.5) * 0.02;
  const lon = 75.5900 + (Math.random() - 0.5) * 0.02;
  const speed = 25.0 + Math.random() * 20.0;
  const heading = Math.random() * 360.0;
  const nowIso = new Date().toISOString();

  // Real GPS Telemetry JSON Payload
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
      'X-Load-Test': 'k6-hpa-benchmark'
    },
    timeout: '4s'
  };

  // Direct Ingress POST to GPS Ingestion service
  http.post(`${BASE_URL}/api/v1/telemetry`, payload, params);

  sleep(0.02);
}
