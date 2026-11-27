// ==============================================================================
// S11 Public Transportation System: k6 Sustained Load Testing Suite (Requirement c)
// Target: Service 2 (GPS Ingestion Service) & HPA Scale-Out Validation
// ==============================================================================

import http from 'k6/http';

// ------------------------------------------------------------------------------
// 100 Concurrent Virtual Users:
// Saturates pod CPU over port-forward tunnel to drive utilization > 50% target
// and trigger GKE Horizontal Pod Autoscaling (HPA) scale-out live.
// ------------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '20s', target: 60 },   // Fast ramp-up to 60 VUs
    { duration: '2m',  target: 100 },  // Sustained peak: 100 VUs (drives CPU to 80-100% > 50% target)
    { duration: '15s', target: 0 },    // Cool-down to 0 VUs (HPA scale-in)
  ],
};

const BASE_URL = __ENV.INGESTION_URL || 'http://localhost:8002';

export default function () {
  http.get(`${BASE_URL}/health`, {
    headers: {
      'Connection': 'keep-alive',
      'X-Load-Test': 'k6-hpa-benchmark'
    },
    timeout: '10s'
  });
}
