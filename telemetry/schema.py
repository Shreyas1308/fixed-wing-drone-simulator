"""
Telemetry data schema for the fixed-wing simulator.

This module defines the standard structure of a telemetry record.
All simulator, logging, and analysis code should use these classes
so field names, types, and units stay consistent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TelemetryRecord:
    """One snapshot of fixed-wing aircraft telemetry."""

    timestamp: datetime
    simulation_time_s: float

    # Position
    latitude_deg: float
    longitude_deg: float
    altitude_m: float

    # Motion
    airspeed_ms: float
    groundspeed_ms: float
    vertical_speed_ms: float
    heading_deg: float

    # Orientation
    roll_deg: float
    pitch_deg: float
    yaw_deg: float

    # Aircraft state
    throttle: float
    battery_percent: float
    flight_mode: str = "MANUAL"

    # Optional extra values, such as wind, control-surface angles, etc.
    extra: dict[str, float | str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert the telemetry record into a JSON-friendly dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "simulation_time_s": self.simulation_time_s,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "altitude_m": self.altitude_m,
            "airspeed_ms": self.airspeed_ms,
            "groundspeed_ms": self.groundspeed_ms,
            "vertical_speed_ms": self.vertical_speed_ms,
            "heading_deg": self.heading_deg,
            "roll_deg": self.roll_deg,
            "pitch_deg": self.pitch_deg,
            "yaw_deg": self.yaw_deg,
            "throttle": self.throttle,
            "battery_percent": self.battery_percent,
            "flight_mode": self.flight_mode,
            **self.extra,
        }


def make_example_record() -> TelemetryRecord:
    """Create an example telemetry record for testing."""
    return TelemetryRecord(
        timestamp=datetime.now(timezone.utc),
        simulation_time_s=0.0,
        latitude_deg=47.3769,
        longitude_deg=8.5417,
        altitude_m=500.0,
        airspeed_ms=25.0,
        groundspeed_ms=24.0,
        vertical_speed_ms=1.5,
        heading_deg=90.0,
        roll_deg=0.0,
        pitch_deg=2.0,
        yaw_deg=90.0,
        throttle=0.65,
        battery_percent=98.0,
        flight_mode="AUTO",
    )


if __name__ == "__main__":
    record = make_example_record()
    print(record)
    print(record.to_dict())