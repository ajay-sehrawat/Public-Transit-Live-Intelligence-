# -*- coding: utf-8 -*-
"""Apache Flink Streaming Job (PyFlink)
Runs on Managed Cluster (Google Cloud Dataproc / AWS EMR / Flink on K8s).
Consumes: 'bus-gps-normalized'
Performs: Stateful, 1-minute tumbling event-time windowed aggregation with watermarking.
Publishes: 'bus-arrival-estimates' and 'bus-route-stats'.
"""

import os
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PyFlinkJob")

try:
    from pyflink.common import WatermarkStrategy, Time, Duration
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import KafkaSource, KafkaSink, KafkaRecordSerializationSchema
    from pyflink.datastream.window import TumblingEventTimeWindows
    from pyflink.datastream.functions import ProcessWindowFunction
    HAS_PYFLINK = True
except ImportError:
    HAS_PYFLINK = False

def run_flink_job():
    """Main execution function for PyFlink streaming job on managed Dataproc."""
    if not HAS_PYFLINK:
        logger.warning("PyFlink is not installed on local system; using Python streaming engine.")
        from stream_processor_engine import StreamProcessorEngine
        engine = StreamProcessorEngine()
        logger.info("Local Flink streaming engine initialized.")
        return

    logger.info("Initializing Apache Flink Execution Environment...")
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(2)
    env.enable_checkpointing(10000) # Checkpoint every 10 seconds to GCS/S3

    kafka_bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    input_topic = "bus-gps-normalized"
    output_topic = "bus-arrival-estimates"

    logger.info(f"Connecting to Kafka at {kafka_bootstrap}")

    # 1. Define Kafka Source
    kafka_source = KafkaSource.builder() \
        .set_bootstrap_servers(kafka_bootstrap) \
        .set_topics(input_topic) \
        .set_group_id("flink-stream-processor-group") \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # 2. Watermark Strategy: BoundedOutOfOrderness (20 seconds)
    watermark_strategy = WatermarkStrategy \
        .for_bounded_out_of_orderness(Duration.of_seconds(20)) \
        .with_timestamp_assigner(lambda event_str, ts: json.loads(event_str).get("event_timestamp", int(datetime.utcnow().timestamp()*1000)))

    # 3. Stream Creation with Event-Time
    stream = env.from_source(kafka_source, watermark_strategy, "KafkaNormalizedGPSSource")

    # Parse JSON
    parsed_stream = stream.map(lambda s: json.loads(s))

    # 4. Keyed Stateful 1-Minute Tumbling Window
    keyed_stream = parsed_stream.key_by(lambda x: (x.get("route_id", "R1"), x.get("bus_id", "B1")))

    class ArrivalEstimateWindowFunction(ProcessWindowFunction):
        def process(self, key, context, elements):
            events = list(elements)
            sample_count = len(events)
            if sample_count == 0:
                return

            total_speed = sum(float(e.get("speed_kmh", 0.0)) for e in events)
            avg_speed_kmh = round(total_speed / sample_count, 2)
            speed_ms = max(1.0, (avg_speed_kmh * 1000.0) / 3600.0)

            latest = events[-1]
            distance = float(latest.get("distance_to_next_stop_meters", 500.0))
            eta_sec = int(distance / speed_ms) + 30

            result = {
                "window_end": context.window().end,
                "route_id": key[0],
                "bus_id": key[1],
                "sample_count": sample_count,
                "rolling_avg_speed_kmh": avg_speed_kmh,
                "next_stop_name": latest.get("next_stop_name", "Transit Stop"),
                "distance_to_stop_meters": distance,
                "eta_seconds": eta_sec,
                "status": "DELAYED" if eta_sec > 300 else "ON_TIME"
            }
            yield json.dumps(result)

    windowed_stream = keyed_stream \
        .window(TumblingEventTimeWindows.of(Time.minutes(1))) \
        .process(ArrivalEstimateWindowFunction())

    # 5. Define Kafka Sink
    kafka_sink = KafkaSink.builder() \
        .set_bootstrap_servers(kafka_bootstrap) \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(output_topic)
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        ) \
        .build()

    windowed_stream.sink_to(kafka_sink)

    logger.info("Submitting Apache Flink DAG to cluster...")
    env.execute("PublicTransitRealtimeArrivalEstimator")

if __name__ == "__main__":
    run_flink_job()

