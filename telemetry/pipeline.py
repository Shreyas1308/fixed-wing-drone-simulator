"""
This module contains the TelemetryPipeline class, which is responsible for processing telemetry data. 
It defines the structure and behavior of the pipeline, including methods for data ingestion, transformation, and output. 
The pipeline can be configured to handle different types of telemetry data and can be extended to support additional processing steps as needed.

NUTSHELL: This module cleans the data and converts it into a TelemetryRecord object.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

import numpy as np

from telemetry.schema import TelemetryRecord

NUMERIC_FIELDS = {
    #"timestamp",
    "simulation_time_s",
    "latitude_deg",
    "longitude_deg",
    "altitude_m",
    "airspeed_ms",
    "groundspeed_ms",
    "vertical_speed_ms",
    "heading_deg",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "throttle",
    "battery_percent",
    "flight_mode",
}

REQUIRED_FIELDS = {
    "timestamp",
    NUMERIC_FIELDS,
}

def clean_raw_data(raw: dict[str, Any]) -> TelemetryRecord:
    """Clean the raw telemetry data."""
    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        raise ValueError(f"Missing required telemetry fields: {missing}")

    cleaned = dict(raw)

    # Parse timestamp
    if isinstance(cleaned["timestamp"], str):
        cleaned["timestamp"] = datetime.fromisoformat(cleaned["timestamp"])
    elif cleaned["timestamp"] is None:
        cleaned["timestamp"] = datetime.now(timezone.utc)

    # Convert numeric fields into a NumPy float array
    try:
        values = np.array(
            [cleaned[field] for field in NUMERIC_FIELDS],
            dtype=np.float64,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"Telemetry values must be numeric: {error}") from error

    # Reject NaN or infinite values
    if not np.all(np.isfinite(values)):
        bad_fields = [
            field
            for field, value in zip(NUMERIC_FIELDS, values)
            if not np.isfinite(value)
        ]
        raise ValueError(f"Invalid numeric values in: {bad_fields}")

    # Put cleaned numeric values back into the record
    for field, value in zip(NUMERIC_FIELDS, values):
        cleaned[field] = float(value)

    # Range validation using NumPy boolean masks
    latitude, longitude = cleaned["latitude_deg"], cleaned["longitude_deg"]
    throttle, battery = cleaned["throttle"], cleaned["battery_percent"]

    if not (-90 <= latitude <= 90):
        raise ValueError("latitude_deg must be between -90 and 90")

    if not (-180 <= longitude <= 180):
        raise ValueError("longitude_deg must be between -180 and 180")

    if not (0 <= throttle <= 1):
        raise ValueError("throttle must be between 0 and 1")

    if not (0 <= battery <= 100):
        raise ValueError("battery_percent must be between 0 and 100")

    return TelemetryRecord(**cleaned)

def calculate_derived_values(records: list[TelemetryRecord]) -> dict[str, np.ndarray]:
    """Calculate derived values from a list of telemetry records."""
    if not records:
        return {}

    time_s = np.array([record.simulation_time_s for record in records])
    altitude_m = np.array([record.altitude_m for record in records])
    airspeed_ms = np.array([record.airspeed_ms for record in records])
    battery_percent = np.array([record.battery_percent for record in records])

    # Calculate altitude change over time, avoiding division by zero
    climb_rate = np.gradient(altitude_m, time_s) if len(records) > 1 else np.array([0.0])

    return {
        "time_s": time_s,
        "altitude_m": altitude_m,
        "airspeed_ms": airspeed_ms,
        "battery_percent": battery_percent,
        "climb_rate_ms": climb_rate,
    }

def process_telemetry_data(raw_data: list[dict[str, Any]]) -> list[TelemetryRecord]:
    """Process a list of raw telemetry data dictionaries into TelemetryRecord objects."""
    valid_records: list[TelemetryRecord] = []
    rejected: list[str] = []

    for index, raw in enumerate(raw_data):
        try:
            valid_records.append(clean_raw_record(raw))
        except (ValueError, TypeError) as error:
            rejected.append(f"Record {index}: {error}")

    if rejected:
        print(f"Accepted {len(valid_records)} records; rejected {len(rejected)}.")
        for message in rejected:
            print(message)

    return valid_records