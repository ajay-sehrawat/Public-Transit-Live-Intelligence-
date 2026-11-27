// ==============================================================================
// S11 Public Transportation System: k6 Sustained Load Testing Suite (Requirement c)
// Target: Service 2 (GPS Ingestion Service) & HPA Scale-Out Validation
// ==============================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';

// ------------------------------------------------------------------------------
// Load Test Stages: Drives CPU > 50% target to trigger HPA scale-out immediately
// ------------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '10s', target: 20 },  // Quick ramp to 20 VUs
    { duration: '1m20s', target: 35 }, // Sustained peak: 35 VUs (drives CPU to 75-90% > 50% target)
    { duration: '10s', target: 0 },   // Cool-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.10'],   // Allow up to 10% during peak autoscaling transition
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

  // 10ms sleep yields ~50 req/s per VU -> 35 VUs * 50 = ~1,750 req/s
  // This drives container CPU to ~80m/100m (80%), triggering HPA scale-up
  sleep(0.01);
}
