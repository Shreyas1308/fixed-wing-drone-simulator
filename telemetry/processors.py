"""
Telemetry processors for the fixed-wing simulator.

Each processor takes one raw telemetry dictionary and returns a
processed telemetry dictionary.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np


Processor = Callable[[dict[str, Any]], dict[str, Any]]


def round_coordinates(
    record: dict[str, Any],
    decimals: int = 6,
) -> dict[str, Any]:
    """Round GPS coordinates to reduce noise and file size."""
    processed = dict(record)

    processed["latitude_deg"] = round(float(record["latitude_deg"]), decimals)
    processed["longitude_deg"] = round(float(record["longitude_deg"]), decimals)

    return processed


def clamp_values(record: dict[str, Any]) -> dict[str, Any]:
    """Keep selected telemetry values within physically sensible ranges."""
    processed = dict(record)

    processed["altitude_m"] = max(0.0, float(record["altitude_m"]))
    processed["throttle"] = min(1.0, max(0.0, float(record["throttle"])))
    processed["battery_percent"] = min(
        100.0,
        max(0.0, float(record["battery_percent"])),
    )

    return processed


def add_flight_metrics(record: dict[str, Any]) -> dict[str, Any]:
    """Add derived single-record flight metrics."""
    processed = dict(record)

    groundspeed_ms = max(float(record.get("groundspeed_ms", 0.0)), 1e-6)
    vertical_speed_ms = float(record.get("vertical_speed_ms", 0.0))

    processed["flight_path_angle_deg"] = float(
        np.degrees(np.arctan2(vertical_speed_ms, groundspeed_ms))
    )

    processed["ground_track_deg"] = float(record["heading_deg"])

    return processed


def apply_processors(
    record: dict[str, Any],
    processors: list[Processor],
) -> dict[str, Any]:
    """Run one telemetry record through a sequence of processors."""
    processed = record

    for processor in processors:
        processed = processor(processed)

    return processed