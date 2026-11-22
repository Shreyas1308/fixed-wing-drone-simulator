"""
Telemetry sources for the fixed-wing simulator.

A source produces raw telemetry dictionaries. It does not validate
the data; validation and cleaning are handled by the pipeline.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any, Iterator


class SimulatedTelemetrySource:
    """Generates simple simulated fixed-wing telemetry."""

    def __init__(
        self,
        start_latitude_deg: float = 47.3769,
        start_longitude_deg: float = 8.5417,
        start_altitude_m: float = 500.0,
        airspeed_ms: float = 25.0,
        heading_deg: float = 90.0,
    ) -> None:
        self.latitude_deg = start_latitude_deg
        self.longitude_deg = start_longitude_deg
        self.altitude_m = start_altitude_m
        self.airspeed_ms = airspeed_ms
        self.heading_deg = heading_deg
        self.simulation_time_s = 0.0

    def _move_aircraft(self, dt_s: float) -> None:
        """Move the simulated aircraft using a basic flat-Earth approximation."""
        heading_rad = math.radians(self.heading_deg)

        meters_per_degree_latitude = 111_320.0
        meters_per_degree_longitude = (
            111_320.0 * math.cos(math.radians(self.latitude_deg))
        )

        north_m = self.airspeed_ms * dt_s * math.cos(heading_rad)
        east_m = self.airspeed_ms * dt_s * math.sin(heading_rad)

        self.latitude_deg += north_m / meters_per_degree_latitude
        self.longitude_deg += east_m / meters_per_degree_longitude

        self.altitude_m += random.uniform(-0.5, 0.8)

    def read(self, dt_s: float = 1.0) -> dict[str, Any]:
        """Return one raw telemetry sample and advance the simulation."""
        self._move_aircraft(dt_s)
        self.simulation_time_s += dt_s
        battery_voltage_v = 12.6 - (self.simulation_time_s * 0.002)
        battery_current_a = 4.0 + throttle * 6.0
        motor_power_w = battery_voltage_v * battery_current_a

        return {
            "timestamp": datetime.now(timezone.utc),
            "simulation_time_s": self.simulation_time_s,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "altitude_m": self.altitude_m,
            "airspeed_ms": self.airspeed_ms,
            "groundspeed_ms": self.airspeed_ms * random.uniform(0.95, 1.05),
            "vertical_speed_ms": random.uniform(-1.0, 1.5),
            "heading_deg": self.heading_deg,
            "roll_deg": random.uniform(-5.0, 5.0),
            "pitch_deg": random.uniform(-3.0, 5.0),
            "yaw_deg": self.heading_deg,
            "throttle": random.uniform(0.55, 0.75),
            "battery_percent": max(
                0.0,
                100.0 - self.simulation_time_s * 0.01,
                ),
            "battery_voltage_v": battery_voltage_v,
            "battery_current_a": battery_current_a,
            "motor_power_w": motor_power_w,
            "flight_mode": "AUTO",
        }

    def stream(
        self,
        count: int,
        dt_s: float = 1.0,
    ) -> Iterator[dict[str, Any]]:
        """Yield a fixed number of telemetry samples."""
        for _ in range(count):
            yield self.read(dt_s=dt_s)