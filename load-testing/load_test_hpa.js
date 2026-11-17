// ==============================================================================
// S11 Public Transportation System: k6 Sustained Load Testing Suite (Requirement c)
// Target: Service 2 (GPS Ingestion Service) & HPA Scale-Out Validation
// ==============================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';

// ------------------------------------------------------------------------------
// Load Test Stages: Sustained High-Throughput Traffic
// ------------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '1m', target: 300 },   // Ramp-up: 0 to 300 Virtual Users (VUs)
    { duration: '3m', target: 800 },   // Sustained peak: 800 VUs (~1,500+ requests/sec)
    { duration: '1m', target: 0 },     // Ramp-down: Cool-down to 0 VUs (HPA scale-in)
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],    // Error rate must remain under 1%
    http_req_duration: ['p(95)<200'],  // 95% of requests must complete under 200ms
  },
};

const BASE_URL = __ENV.INGESTION_URL || 'http://localhost:8002';

// Simulated Active Fleet & Route Coordinates
const BUS_FLEET = ['BUS-101', 'BUS-102', 'BUS-103', 'BUS-201', 'BUS-202', 'BUS-401'];
const COORD_BOUNDS = {
  minLat: 28.3550, maxLat: 28.3752,
  minLon: 75.5810, maxLon: 75.6050
};

function getRandomArbitrary(min, max) {
  return Math.random() * (max - min) + min;
}

export default function () {
  // Select random bus from authorized registry
  const busId = BUS_FLEET[Math.floor(Math.random() * BUS_FLEET.length)];
  const lat = getRandomArbitrary(COORD_BOUNDS.minLat, COORD_BOUNDS.maxLat);
  const lon = getRandomArbitrary(COORD_BOUNDS.minLon, COORD_BOUNDS.maxLon);
  const speed = getRandomArbitrary(15.0, 50.0);
  const heading = getRandomArbitrary(0.0, 360.0);
  const nowIso = new Date().toISOString();

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
    timeout: '5s'
  };

  const res = http.post(`${BASE_URL}/api/v1/telemetry`, payload, params);

  // Validate response status 202 Accepted
  check(res, {
    'status is 202 Accepted': (r) => r.status === 202,
    'has correlation_id': (r) => r.json('correlation_id') !== undefined,
  });

  // Small random sleep to simulate real IoT sensor transmission cadence
  sleep(getRandomArbitrary(0.05, 0.2));
}

