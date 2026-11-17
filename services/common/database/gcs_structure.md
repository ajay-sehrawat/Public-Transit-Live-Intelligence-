# Google Cloud Storage Object Architecture (Storage Product 3: Object Store)
## Requirement (g): Object Store for Raw Telemetry Dumps & Asynchronous Serverless Triggers

Bucket Name: `gs://transit-telemetry-raw-archive-<PROJECT_ID>`  
Region: `US` Multi-Region (Always-Free Tier: 5 GB-months of standard storage)

---

### Folder Layout & Object Hierarchy

```
gs://transit-telemetry-raw-archive-<PROJECT_ID>/
│
├── raw-telemetry-dumps/            # Daily/Hourly raw GPS batches from buses
│   └── year=2026/
│       └── month=11/
│           └── day=18/
│               └── bus-gps-batch-20261118T010000Z.json.gz
│
├── gtfs-schedules/                 # General Transit Feed Specification (GTFS) schedules
│   ├── routes.txt
│   ├── stops.txt
│   ├── stop_times.txt
│   └── trips.txt
│
├── passenger-tap-batches/          # Smartcard / NFC tap-in batch dumps
│   └── tap-events-20261118-0100.parquet
│
└── incidents/                      # Roadblock, maintenance & traffic disruption reports
    └── incident-report-20261118-01.json   # <-- TRIGGER: Triggers Service 7 (Cloud Function)
```

### Eventarc / Cloud Storage Event Integration (Requirement b):
When an incident or roadblock JSON report is uploaded to `incidents/`, Google Cloud Storage fires an `object.finalize` event via Cloud Pub/Sub, automatically invoking the **Delay Alert Service (Cloud Function 2nd Gen)** asynchronously!

