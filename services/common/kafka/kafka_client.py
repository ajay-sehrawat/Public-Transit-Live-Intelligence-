# -*- coding: utf-8 -*-
"""Kafka Producer & Consumer Wrapper with In-Memory Broker Simulator
Supports Confluent Cloud / Apache Kafka in cloud deployment and in-memory message queue locally.
"""

import os
import json
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("KafkaClient")

try:
    from kafka import KafkaProducer as RealKafkaProducer
    from kafka import KafkaConsumer as RealKafkaConsumer
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False


class InMemoryKafkaBroker:
    """Thread-safe in-memory Kafka broker simulator supporting topics and partitions."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InMemoryKafkaBroker, cls).__new__(cls)
                cls._instance._init_broker()
            return cls._instance

    def _init_broker(self):
        self.topics: Dict[str, List[Dict[str, Any]]] = {
            "bus-gps-raw": [],
            "bus-gps-normalized": [],
            "bus-arrival-estimates": [],
            "bus-delay-alerts": [],
            "bus-route-stats": []
        }
        self.subscribers: Dict[str, List[Callable]] = {}
        self.lock = threading.RLock()

    def reset(self):
        with self.lock:
            self._init_broker()

    def produce(self, topic: str, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            if topic not in self.topics:
                self.topics[topic] = []

            offset = len(self.topics[topic])
            record = {
                "topic": topic,
                "key": key,
                "value": value,
                "offset": offset,
                "timestamp": int(time.time() * 1000)
            }
            self.topics[topic].append(record)

            # Trigger asynchronous subscriber callbacks
            if topic in self.subscribers:
                for callback in list(self.subscribers[topic]):
                    try:
                        callback(record)
                    except Exception as e:
                        logger.error(f"Error in Kafka subscriber for {topic}: {e}")

            return record

    def get_messages(self, topic: str, from_offset: int = 0) -> List[Dict[str, Any]]:
        with self.lock:
            if topic not in self.topics:
                return []
            return list(self.topics[topic][from_offset:])

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        with self.lock:
            if topic not in self.subscribers:
                self.subscribers[topic] = []
            if callback not in self.subscribers[topic]:
                self.subscribers[topic].append(callback)


class TransitKafkaProducer:
    """Unified Kafka Producer."""

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.real_producer = None
        self.in_memory = InMemoryKafkaBroker()

        if HAS_KAFKA and "localhost" not in self.bootstrap_servers:
            try:
                self.real_producer = RealKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    acks="all",
                    retries=3
                )
                logger.info(f"[✓] Connected to live Kafka cluster at {self.bootstrap_servers}")
            except Exception as e:
                logger.warning(f"Could not connect to live Kafka at {self.bootstrap_servers}: {e}. Using in-memory broker.")
                self.real_producer = None

    def send(self, topic: str, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        """Publishes message to Kafka topic."""
        if self.real_producer:
            try:
                future = self.real_producer.send(topic, key=key, value=value)
                metadata = future.get(timeout=5)
                return {"topic": metadata.topic, "partition": metadata.partition, "offset": metadata.offset}
            except Exception as e:
                logger.error(f"Error publishing to real Kafka: {e}")

        # Fallback to in-memory broker
        return self.in_memory.produce(topic, key, value)

    def flush(self):
        if self.real_producer:
            self.real_producer.flush()


class TransitKafkaConsumer:
    """Unified Kafka Consumer."""

    def __init__(self, topic: str, group_id: str = "transit-group", bootstrap_servers: Optional[str] = None):
        self.topic = topic
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.real_consumer = None
        self.in_memory = InMemoryKafkaBroker()
        self.current_offset = 0

        if HAS_KAFKA and "localhost" not in self.bootstrap_servers:
            try:
                self.real_consumer = RealKafkaConsumer(
                    self.topic,
                    group_id=self.group_id,
                    bootstrap_servers=self.bootstrap_servers,
                    auto_offset_reset="earliest",
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    key_deserializer=lambda k: k.decode("utf-8") if k else None,
                    enable_auto_commit=True
                )
                logger.info(f"[✓] Kafka consumer listening to topic '{self.topic}' (group: {self.group_id})")
            except Exception as e:
                logger.warning(f"Could not connect live consumer: {e}. Using in-memory consumer.")
                self.real_consumer = None

    def poll(self, max_records: int = 100) -> List[Dict[str, Any]]:
        """Polls available messages from the topic."""
        if self.real_consumer:
            raw_records = self.real_consumer.poll(timeout_ms=1000, max_records=max_records)
            messages = []
            for tp, records in raw_records.items():
                for r in records:
                    messages.append({
                        "topic": r.topic,
                        "key": r.key,
                        "value": r.value,
                        "offset": r.offset,
                        "timestamp": r.timestamp
                    })
            return messages

        # In-Memory polling
        all_messages = self.in_memory.get_messages(self.topic, from_offset=self.current_offset)
        if all_messages:
            self.current_offset += len(all_messages)
        return all_messages

    def subscribe_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registers asynchronous callback invoked whenever new message is published to topic."""
        self.in_memory.subscribe(self.topic, callback)

