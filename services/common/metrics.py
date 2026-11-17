# -*- coding: utf-8 -*-
"""Shared Prometheus Metrics Utilities for Transit Microservices (Requirement h)"""

import time
from typing import Dict, List, Any


def format_prometheus_counter(metric_name: str, value: int, help_text: str, labels: Dict[str, str] = None) -> str:
    """Formats a single Prometheus counter."""
    label_str = ""
    if labels:
        label_str = "{" + ",".join([f'{k}="{v}"' for k, v in labels.items()]) + "}"
    lines = [
        f"# HELP {metric_name} {help_text}",
        f"# TYPE {metric_name} counter",
        f"{metric_name}{label_str} {value}"
    ]
    return "\n".join(lines)


def format_prometheus_gauge(metric_name: str, value: float, help_text: str, labels: Dict[str, str] = None) -> str:
    """Formats a single Prometheus gauge."""
    label_str = ""
    if labels:
        label_str = "{" + ",".join([f'{k}="{v}"' for k, v in labels.items()]) + "}"
    lines = [
        f"# HELP {metric_name} {help_text}",
        f"# TYPE {metric_name} gauge",
        f"{metric_name}{label_str} {value}"
    ]
    return "\n".join(lines)


def generate_prometheus_metrics(service_name: str, request_counts: Dict[str, int], extra_gauges: Dict[str, float] = None) -> str:
    """Generates complete Prometheus scrape payload."""
    lines = [
        f"# HELP transit_http_requests_total Total HTTP requests handled by {service_name}",
        "# TYPE transit_http_requests_total counter"
    ]
    for endpoint, count in request_counts.items():
        lines.append(f'transit_http_requests_total{{service="{service_name}",endpoint="{endpoint}"}} {count}')

    if extra_gauges:
        for name, val in extra_gauges.items():
            lines.append(f"# HELP transit_{name} Operational metric for {service_name}")
            lines.append(f"# TYPE transit_{name} gauge")
            lines.append(f'transit_{name}{{service="{service_name}"}} {val}')

    return "\n".join(lines) + "\n"

