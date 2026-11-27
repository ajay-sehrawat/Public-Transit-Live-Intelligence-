// ==============================================================================
// S11 Public Transportation System: k6 Sustained Load Testing Suite (Requirement c)
// Target: Service 2 (GPS Ingestion Service) & HPA Scale-Out Validation
// ==============================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';

// ------------------------------------------------------------------------------
// Load Test Stages: Sustained High-Throughput Traffic (Drives CPU > 50% for HPA)
// GKE Metrics Server requires ~45-60s of sustained load to compute windowed CPU
// ------------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '20s', target: 50 },  // Fast ramp-up to 50 Virtual Users
    { duration: '2m',  target: 60 },  // Sustained peak: 60 VUs (~800-1200 req/s, drives CPU > 50%)
    { duration: '20s', target: 0 },   // Cool-down to 0 VUs (HPA scale-in)
  ],
  thresholds: {
    http_req_failed: ['rate<0.25'],   // Tolerant of pod restart / scale-out handoffs
  },
};

const BASE_URL = __ENV.INGESTION_URL || 'http://localhost:8002';

export default function () {
  const res = http.get(`${BASE_URL}/health`, {
    headers: {
      'Connection': 'keep-alive',
      'X-Load-Test': 'k6-hpa-benchmark'
    },
    timeout: '5s'
  });

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(0.01);
}
