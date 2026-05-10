#!/usr/bin/env python3

from __future__ import annotations

import requests


PROMETHEUS_URL = "http://192.168.56.10:9090"


def query_prometheus(query: str):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    return data["data"]["result"]


def get_cpu_usage():
    query = """
    100 - (
      avg by(instance)(
        rate(node_cpu_seconds_total{mode="idle"}[1m])
      ) * 100
    )
    """

    return query_prometheus(query)


def get_memory_usage():
    query = """
    (
      1 -
      (
        node_memory_MemAvailable_bytes
        /
        node_memory_MemTotal_bytes
      )
    ) * 100
    """

    return query_prometheus(query)