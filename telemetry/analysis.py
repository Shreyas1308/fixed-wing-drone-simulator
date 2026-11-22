"""
Telemetry analysis and visualization for the fixed-wing simulator.

This module works with multiple telemetry records. It calculates
flight metrics and creates Matplotlib plots.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from telemetry.schema import TelemetryRecord


def records_to_arrays(records: list[TelemetryRecord]) -> dict[str, np.ndarray]:
    """Convert telemetry records into NumPy arrays for analysis."""
    if not records:
        raise ValueError("No telemetry records provided")

    return {
        "time_s": np.array([record.simulation_time_s for record in records]),
        "altitude_m": np.array([record.altitude_m for record in records]),
        "airspeed_ms": np.array([record.airspeed_ms for record in records]),
        "groundspeed_ms": np.array([record.groundspeed_ms for record in records]),
        "vertical_speed_ms": np.array(
            [record.vertical_speed_ms for record in records]
        ),
        "heading_deg": np.array([record.heading_deg for record in records]),
        "roll_deg": np.array([record.roll_deg for record in records]),
        "pitch_deg": np.array([record.pitch_deg for record in records]),
        "yaw_deg": np.array([record.yaw_deg for record in records]),
        "throttle": np.array([record.throttle for record in records]),
        "battery_percent": np.array(
            [record.battery_percent for record in records]
        ),
        "battery_voltage_v": np.array(
            [
                record.battery_voltage_v
                if record.battery_voltage_v is not None
                else np.nan
                for record in records
            ]
        ),
        "battery_current_a": np.array(
            [
                record.battery_current_a
                if record.battery_current_a is not None
                else np.nan
                for record in records
            ]
        ),
        "latitude_deg": np.array([record.latitude_deg for record in records]),
        "longitude_deg": np.array([record.longitude_deg for record in records]),
    }


def calculate_power_metrics(
    data: dict[str, np.ndarray],
) -> dict[str, np.ndarray | float | None]:
    """Calculate electrical power and energy metrics."""
    battery_voltage_v = data.get("battery_voltage_v")
    battery_current_a = data.get("battery_current_a")

    if battery_voltage_v is None or battery_current_a is None:
        return {
            "motor_power_w": None,
            "average_power_w": None,
            "total_energy_wh": None,
        }

    motor_power_w = battery_voltage_v * battery_current_a
    time_s = data["time_s"]
    valid_samples = (
        np.isfinite(battery_voltage_v)
        & np.isfinite(battery_current_a)
        & np.isfinite(time_s)
    )

    if not np.any(valid_samples):
        return {
            "motor_power_w": None,
            "average_power_w": None,
            "total_energy_wh": None,
        }

    if np.count_nonzero(valid_samples) > 1:
        average_power_w = float(np.mean(motor_power_w[valid_samples]))
        total_energy_wh = float(
            np.trapezoid(
                motor_power_w[valid_samples],
                time_s[valid_samples],
            )
            / 3600.0
        )
    else:
        average_power_w = float(motor_power_w[valid_samples][0])
        total_energy_wh = 0.0

    return {
        "motor_power_w": motor_power_w,
        "average_power_w": average_power_w,
        "total_energy_wh": total_energy_wh,
    }


def calculate_flight_metrics(
    data: dict[str, np.ndarray],
) -> dict[str, np.ndarray | float]:
    """Calculate common fixed-wing flight metrics."""
    time_s = data["time_s"]
    altitude_m = data["altitude_m"]
    groundspeed_ms = data["groundspeed_ms"]
    vertical_speed_ms = data["vertical_speed_ms"]
    heading_deg = data["heading_deg"]

    climb_rate_ms = (
        np.gradient(altitude_m, time_s)
        if len(time_s) > 1
        else np.array([0.0])
    )

    flight_path_angle_deg = np.degrees(
        np.arctan2(
            vertical_speed_ms,
            np.maximum(groundspeed_ms, 1e-6),
        )
    )

    if len(heading_deg) > 1:
        heading_change = np.diff(heading_deg)
        heading_change = (heading_change + 180) % 360 - 180

        dt = np.diff(time_s)
        turn_rate_deg_s = np.concatenate(
            ([0.0], heading_change / np.maximum(dt, 1e-6))
        )
    else:
        turn_rate_deg_s = np.array([0.0])

    if len(time_s) > 1:
        dt = np.diff(time_s)
        total_distance_m = float(np.sum(groundspeed_ms[1:] * dt))
    else:
        total_distance_m = 0.0

    if len(time_s) > 1:
        elapsed_minutes = (time_s[-1] - time_s[0]) / 60.0
        battery_used_percent = (
            data["battery_percent"][0] - data["battery_percent"][-1]
        )

        battery_drain_percent_per_min = (
            battery_used_percent / elapsed_minutes
            if elapsed_minutes > 0
            else 0.0
        )
    else:
        battery_drain_percent_per_min = 0.0

    return {
        "climb_rate_ms": climb_rate_ms,
        "flight_path_angle_deg": flight_path_angle_deg,
        "turn_rate_deg_s": turn_rate_deg_s,
        "total_distance_m": total_distance_m,
        "battery_drain_percent_per_min": battery_drain_percent_per_min,
    }

def calculate_gps_distance(
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
) -> float:
    """Calculate total GPS distance in meters using the haversine formula."""
    earth_radius_m = 6_371_000.0

    lat_rad = np.radians(latitude_deg)
    lon_rad = np.radians(longitude_deg)

    delta_lat = np.diff(lat_rad)
    delta_lon = np.diff(lon_rad)

    a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat_rad[:-1])
        * np.cos(lat_rad[1:])
        * np.sin(delta_lon / 2) ** 2
    )

    segment_distances = (
        2
        * earth_radius_m
        * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1 - a)))
    )

    return float(np.sum(segment_distances))

def calculate_turn_radius(
    groundspeed_ms: np.ndarray,
    turn_rate_deg_s: np.ndarray,
) -> np.ndarray:
    """Calculate instantaneous turn radius in meters."""
    turn_rate_rad_s = np.radians(turn_rate_deg_s)

    safe_turn_rate = np.where(
        np.abs(turn_rate_rad_s) > 1e-6,
        turn_rate_rad_s,
        np.nan,
    )

    return groundspeed_ms / safe_turn_rate

def calculate_turn_coordination(
    roll_deg: np.ndarray,
    airspeed_ms: np.ndarray,
    turn_rate_deg_s: np.ndarray,
) -> np.ndarray:
    """Compare actual turn rate with the turn rate expected from bank angle."""
    gravity_ms2 = 9.81

    roll_rad = np.radians(roll_deg)
    airspeed_ms = np.maximum(airspeed_ms, 1e-6)

    expected_turn_rate_rad_s = gravity_ms2 * np.tan(roll_rad) / airspeed_ms
    expected_turn_rate_deg_s = np.degrees(expected_turn_rate_rad_s)

    return turn_rate_deg_s - expected_turn_rate_deg_s

def estimate_remaining_endurance_minutes(
    battery_percent: np.ndarray,
    battery_drain_percent_per_min: float,
) -> float:
    """Estimate remaining flight time in minutes from battery drain rate."""
    if battery_drain_percent_per_min <= 0:
        return float("inf")

    current_battery_percent = float(battery_percent[-1])

    return current_battery_percent / battery_drain_percent_per_min

def calculate_wind_speed_estimate(
    airspeed_ms: np.ndarray,
    groundspeed_ms: np.ndarray,
) -> np.ndarray:
    """Estimate wind magnitude using the difference between airspeed and groundspeed."""
    return groundspeed_ms - airspeed_ms

#stall_speed_ms: float = 12.0
def calculate_stall_margin(
    airspeed_ms: np.ndarray,
    stall_speed_ms: float = 12.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate margin above stall speed in m/s and as a ratio."""
    margin_ms = airspeed_ms - stall_speed_ms
    margin_ratio = airspeed_ms / max(stall_speed_ms, 1e-6)

    return margin_ms, margin_ratio

def calculate_distance_from_center(
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
    center_latitude_deg: float,
    center_longitude_deg: float,
) -> np.ndarray:
    """Calculate distance from each GPS point to a center point in meters."""
    earth_radius_m = 6_371_000.0

    lat_rad = np.radians(latitude_deg)
    lon_rad = np.radians(longitude_deg)
    center_lat_rad = np.radians(center_latitude_deg)
    center_lon_rad = np.radians(center_longitude_deg)

    delta_lat = center_lat_rad - lat_rad
    delta_lon = center_lon_rad - lon_rad

    a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat_rad)
        * np.cos(center_lat_rad)
        * np.sin(delta_lon / 2) ** 2
    )

    return (
        2
        * earth_radius_m
        * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1 - a)))
    )


def detect_loiter(
    latitude_deg: np.ndarray,
    longitude_deg: np.ndarray,
    radius_m: float = 50.0,
    minimum_points: int = 20,
) -> bool:
    """Return True if the UAV remains within a circular area."""
    if len(latitude_deg) < minimum_points:
        return False

    center_lat = float(np.mean(latitude_deg))
    center_lon = float(np.mean(longitude_deg))

    distances = calculate_distance_from_center(
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        center_latitude_deg=center_lat,
        center_longitude_deg=center_lon,
    )

    return bool(np.mean(distances) <= radius_m)

def detect_anomalies(
    data: dict[str, np.ndarray],
    max_roll_deg: float = 45.0,
    max_pitch_deg: float = 30.0,
    max_climb_rate_ms: float = 10.0,
    battery_drop_percent: float = 5.0,
) -> list[str]:
    """Detect basic telemetry anomalies."""
    anomalies: list[str] = []

    if np.any(np.abs(data["roll_deg"]) > max_roll_deg):
        anomalies.append("Excessive roll angle detected")

    if np.any(np.abs(data["pitch_deg"]) > max_pitch_deg):
        anomalies.append("Excessive pitch angle detected")

    climb_rate = np.gradient(
        data["altitude_m"],
        data["time_s"],
    )

    if np.any(np.abs(climb_rate) > max_climb_rate_ms):
        anomalies.append("Unusually high climb or descent rate detected")

    battery_drop = data["battery_percent"][0] - data["battery_percent"][-1]

    if battery_drop > battery_drop_percent:
        anomalies.append("Large battery drop detected")

    return anomalies

def calculate_advanced_flight_metrics(
    data: dict[str, np.ndarray],
    stall_speed_ms: float = 12.0,
) -> dict[str, np.ndarray | float]:
    """Calculate additional fixed-wing flight metrics."""
    basic_metrics = calculate_flight_metrics(data)

    turn_rate_deg_s = basic_metrics["turn_rate_deg_s"]

    turn_radius_m = calculate_turn_radius(
        groundspeed_ms=data["groundspeed_ms"],
        turn_rate_deg_s=turn_rate_deg_s,
    )

    turn_coordination_deg_s = calculate_turn_coordination(
        roll_deg=data["roll_deg"],
        airspeed_ms=data["airspeed_ms"],
        turn_rate_deg_s=turn_rate_deg_s,
    )

    wind_speed_ms = calculate_wind_speed_estimate(
        airspeed_ms=data["airspeed_ms"],
        groundspeed_ms=data["groundspeed_ms"],
    )

    stall_margin_ms, stall_margin_ratio = calculate_stall_margin(
        airspeed_ms=data["airspeed_ms"],
        stall_speed_ms=stall_speed_ms,
    )

    gps_distance_m = calculate_gps_distance(
        latitude_deg=data["latitude_deg"],
        longitude_deg=data["longitude_deg"],
    )

    remaining_endurance_min = estimate_remaining_endurance_minutes(
        battery_percent=data["battery_percent"],
        battery_drain_percent_per_min=float(
            basic_metrics["battery_drain_percent_per_min"]
        ),
    )

    return {
        **basic_metrics,
        "turn_radius_m": turn_radius_m,
        "turn_coordination_deg_s": turn_coordination_deg_s,
        "wind_speed_ms": wind_speed_ms,
        "stall_margin_ms": stall_margin_ms,
        "stall_margin_ratio": stall_margin_ratio,
        "gps_distance_m": gps_distance_m,
        "remaining_endurance_min": remaining_endurance_min,
    }

def plot_flight_summary(
    records: list[TelemetryRecord],
    save_path: str | Path | None = None,
) -> None:
    """Create a four-panel telemetry summary plot."""
    data = records_to_arrays(records)
    metrics = calculate_flight_metrics(data)
    time_s = data["time_s"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Fixed-Wing Telemetry Summary")

    ax = axes[0, 0]
    ax.plot(time_s, data["altitude_m"], label="Altitude")
    ax.plot(time_s, metrics["climb_rate_ms"], label="Climb rate")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Altitude (m) / climb rate (m/s)")
    ax.legend()
    ax.grid(True)

    ax = axes[0, 1]
    ax.plot(time_s, data["airspeed_ms"], label="Airspeed")
    ax.plot(time_s, data["groundspeed_ms"], label="Groundspeed")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Speed (m/s)")
    ax.legend()
    ax.grid(True)

    ax = axes[1, 0]
    ax.plot(time_s, data["roll_deg"], label="Roll")
    ax.plot(time_s, data["pitch_deg"], label="Pitch")
    ax.plot(time_s, data["heading_deg"], label="Heading")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Angle (degrees)")
    ax.legend()
    ax.grid(True)

    ax = axes[1, 1]
    ax.plot(time_s, data["battery_percent"], label="Battery")
    ax.plot(time_s, data["throttle"] * 100, label="Throttle (%)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Percent")
    ax.legend()
    ax.grid(True)

    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=200)
        plt.close(fig)
    else:
        plt.show()


def plot_power_usage(
    records: list[TelemetryRecord],
    save_path: str | Path | None = None,
) -> None:
    """Plot battery voltage, current, and motor power."""
    data = records_to_arrays(records)
    power_metrics = calculate_power_metrics(data)
    time_s = data["time_s"]

    if power_metrics["motor_power_w"] is None:
        print("Power telemetry is not available.")
        return

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    fig.suptitle("Power Usage")

    axes[0].plot(time_s, data["battery_voltage_v"], color="tab:blue")
    axes[0].set_ylabel("Battery voltage (V)")
    axes[0].grid(True)

    axes[1].plot(time_s, data["battery_current_a"], color="tab:orange")
    axes[1].set_ylabel("Battery current (A)")
    axes[1].grid(True)

    axes[2].plot(
        time_s,
        power_metrics["motor_power_w"],
        color="tab:red",
    )
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("Motor power (W)")
    axes[2].grid(True)

    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=200)
        plt.close(fig)
    else:
        plt.show()


def plot_gps_track(
    records: list[TelemetryRecord],
    save_path: str | Path | None = None,
) -> None:
    """Plot the UAV GPS ground track."""
    data = records_to_arrays(records)

    plt.figure(figsize=(8, 8))
    plt.plot(
        data["longitude_deg"],
        data["latitude_deg"],
        marker="o",
        linewidth=1,
    )
    plt.xlabel("Longitude (degrees)")
    plt.ylabel("Latitude (degrees)")
    plt.title("GPS Ground Track")
    plt.axis("equal")
    plt.grid(True)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, dpi=200)
        plt.close()
    else:
        plt.show()