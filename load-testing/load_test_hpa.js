// ==============================================================================
// S11 Public Transportation System: k6 Sustained Load Testing Suite (Requirement c)
// Target: Service 2 (GPS Ingestion Service) & HPA Scale-Out Validation
// ==============================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';

// ------------------------------------------------------------------------------
// Load Test Stages: Sustained High-Throughput Traffic (Optimized for GKE Nodes)
// ------------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '15s', target: 8 },    // Ramp-up: 8 Virtual Users
    { duration: '1m30s', target: 15 }, // Sustained peak: 15 VUs (~150 req/s, keeps CPU at 70-80% > 50% target)
    { duration: '15s', target: 0 },    // Ramp-down: Cool-down to 0 VUs
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],    // Error rate under 5%
    http_req_duration: ['p(95)<1000'], // 95% under 1s
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

  const targetPath = __ENV.TARGET_PATH || '/health';
  let res;

  if (targetPath === '/health') {
    res = http.get(`${BASE_URL}/health`, {
      headers: {
        'Connection': 'keep-alive',
        'X-Load-Test': 'k6-hpa-benchmark'
      },
      timeout: '10s'
    });
    check(res, {
      'status is 200 OK': (r) => r.status === 200,
      'service is UP': (r) => r.status === 200 && r.body ? r.json('status') === 'UP' : false,
    });
  } else {
    res = http.post(`${BASE_URL}${targetPath}`, payload, {
      headers: {
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
        'X-Load-Test': 'k6-hpa-benchmark'
      },
      timeout: '10s'
    });
    check(res, {
      'status is 200/202': (r) => r.status === 200 || r.status === 202,
    });
  }

  // Paced sleep (~10-12 req/s per VU) keeps CPU high (~75m/100m) while preventing port-forward socket drop
  sleep(0.08);
}

