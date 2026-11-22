# Fixed-Wing Drone Simulator & Telemetry Analysis Framework

An interactive fixed-wing flight simulator and a developing telemetry framework built with Python, Pygame, and OpenGL. Fly a simplified aircraft in a 3D scene, record flight data, and use the framework for consistent telemetry handling and future analysis tools.

> **Note:** This is an illustrative simulator, not a validated flight model. It is intended for experimentation and learning, not real-world flight planning or control.

## Screenshots

<table>
  <tr>
    <td><img src="screenshots/Screenshot%202026-10-09%20135903.png" alt="Simulator screenshot from October 9, 2026" width="100%"></td>
    <td><img src="screenshots/Screenshot%202026-10-24%20182951.png" alt="Simulator screenshot from October 24, 2026" width="100%"></td>
  </tr>
  <tr>
    <td><img src="screenshots/Screenshot%202026-10-24%20183034.png" alt="Simulator screenshot from October 24, 2026" width="100%"></td>
    <td><img src="screenshots/Screenshot%202026-10-24%20183355.png" alt="Simulator screenshot from October 24, 2026" width="100%"></td>
  </tr>
  <tr>
    <td><img src="screenshots/Screenshot%202026-10-28%20170204.png" alt="Simulator screenshot from October 28, 2026" width="100%"></td>
    <td><img src="screenshots/Screenshot%202026-10-28%20170252.png" alt="Simulator screenshot from October 28, 2026" width="100%"></td>
  </tr>
</table>

## Features

- 3D aircraft and ground rendering with OpenGL
- Keyboard controls for roll, pitch, yaw, and throttle
- Adjustable wind, gusts, and rain, with atmospheric and rain-particle effects
- Wind affects the aircraft's movement through the world
- Pause and reset controls
- Timestamped CSV flight logs, saved in the `flight_logs/` folder
- Telemetry fields for position, altitude, speed, throttle, attitude, and pause state

## Requirements

- Python 3
- A graphics environment with OpenGL support

Python packages are listed in [`requirements.txt`](requirements.txt).

## Setup and run

Open a terminal in the project folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

If PowerShell blocks virtual-environment activation, you can skip activation and run the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

The simulator opens a 1280 × 720 window. Its title displays the current speed and altitude, recording status (`REC` or `NOT RECORDING`), and the `L` key shortcut.

## Controls

| Key | Action |
| --- | --- |
| `A` / `Left Arrow` | Roll left |
| `D` / `Right Arrow` | Roll right |
| `W` / `Up Arrow` | Pitch up |
| `S` / `Down Arrow` | Pitch down |
| `Q` | Yaw left |
| `E` | Yaw right |
| `Left Shift` / `Right Shift` | Increase throttle |
| `Left Ctrl` / `Right Ctrl` | Decrease throttle |
| `Space` | Pause or resume |
| `R` | Reset the aircraft state |
| `L` | Start or stop CSV telemetry recording |
| `Esc` or close the window | Exit |

### Map behavior and geographic coordinates

- The aircraft's local position `(x=0, z=0)` corresponds to the selected home coordinates configured in `main.py`.
- To use a local map, put its `.osm` file in `simulator/maps/`. The current setting loads `simulator/maps/map.osm` directly. Make sure the selected home coordinates lie within the map's geographic bounds.
- To use a differently named map, update the `osm_file` assignment in `main.py` to the new filename. For example:

  ```python
  osm_file = project_root / "simulator" / "maps" / "my_area.osm"
  ```

- When changing maps, replace `map.osm` in `simulator/maps/` or update the path above to match the new file.
- Without a local `map.osm`, the simulator loads the area around the selected home coordinates from a matching cache or downloads it from Overpass. Downloaded data is cached in the project `map_cache/` folder, which is ignored by Git.
- If no local map is available and the download or cache read fails, the simulator prints a warning and continues without OSM roads and buildings. Run it again when the map service is available to populate the cache. If you change the home coordinates or map size, a different cache entry is needed.
- The ground grid follows the aircraft and has a 500 m radius. At longer distances, map features may extend beyond the visible ground. For an initial test, stay near the origin or increase `grid_radius` in `Renderer.draw_ground`.
- Buildings are visual only and do not prevent the aircraft from passing through them.
- If the origin is inside a building footprint, the aircraft may appear over or inside that building. Choose a suitable home location.
- OpenStreetMap building height tags can be missing, so some buildings use the loader's fallback height.

To convert the aircraft's local position back to geographic coordinates:

```python
latitude, longitude = coordinates.to_geographic(
    drone.state.x,
    drone.state.z,
)
```

These coordinates can be added to telemetry separately if needed.

### Weather controls

| Key | Action |
| --- | --- |
| `F1` | Calm preset |
| `F2` | Windy preset |
| `F3` | Rain preset |
| `F4` | Heavy-rain preset |
| `1` / `2` | Decrease / increase wind speed |
| `3` / `4` | Decrease / increase rain rate |
| `5` / `6` | Rotate wind direction |
| `7` / `8` | Decrease / increase gust strength |

The current wind speed, direction, and rain rate are printed in the terminal when a weather setting changes. Weather and rain particles pause with the aircraft.

## Flight telemetry

Press `L` to start recording. The simulator creates the `flight_logs/` folder if needed, then creates a file named `flight_log_YYYYMMDD_HHMMSS.csv` inside it and immediately writes the current telemetry sample. While recording, it writes additional samples at approximately 10 samples per simulated second and flushes each row to the file.

Press `L` again to stop recording and close the file. If you exit while recording, the simulator closes the file automatically. The path to the most recent CSV log is printed in the terminal. Each new recording creates a separate CSV file in `flight_logs/`.

The CSV includes:

| Column | Description |
| --- | --- |
| `time_s` | Elapsed unpaused simulation time, in seconds |
| `x_m`, `altitude_m`, `z_m` | Aircraft position, in meters |
| `speed_mps` | Aircraft speed, in meters per second |
| `throttle_percent` | Throttle setting, from 0 to 100 |
| `roll_deg`, `pitch_deg`, `yaw_deg` | Aircraft attitude angles, in degrees |
| `paused` | Whether the simulator was paused when the row was written |

Open a flight log in a spreadsheet application to inspect it. The simulator does not currently plot live data; post-flight plotting functions are described below.

## Telemetry processing and analysis framework

The telemetry framework is being developed as a separate, reusable path for turning raw flight samples into validated records and analysis results. The intended flow is:

```text
telemetry/sources.py
        |  Raw telemetry dictionary
        v
telemetry/processors.py
        |  Cleaned and enriched telemetry
        v
telemetry/pipeline.py
        |  Validated TelemetryRecord
        v
telemetry/session.py
        |  Flight session and metadata
        v
telemetry/sinks/
        |  CSV and/or JSON flight logs (planned)
        v
telemetry/analysis.py
        |  Flight metrics, plots, and anomaly findings
        +------> Analysis results returned to the caller
        +------> Plots shown or saved to a caller-selected path

Current simulator CSV logs  --->  flight_logs/
Manually captured UI images  --->  screenshots/
```

This diagram describes the planned framework flow, not an automatic end-to-end process yet. The framework is separate from the simulator's existing `L`-key CSV logger.

### What each stage does

- **Sources (`telemetry/sources.py`)** are the input layer, intended to provide raw telemetry dictionaries. The included simulated source models position, motion, orientation, throttle, battery, and flight-mode values.
- **Processors (`telemetry/processors.py`)** can be composed to round GPS coordinates, clamp selected values to configured ranges, and add per-sample flight-path-angle and ground-track fields.
- **Pipeline and schema (`telemetry/pipeline.py`, `telemetry/schema.py`)** validate required values, parse timestamps, check numeric fields and ranges, handle optional battery voltage/current/power values, and represent accepted samples as `TelemetryRecord` objects.
- **Sessions (`telemetry/session.py`)** define a flight ID, start/end timestamps, and record count, and are intended to pass records to configured sinks. Session-to-sink integration is still in development.
- **Sinks (`telemetry/sinks/`)** are intended to write records to formats such as CSV or JSON. The sink modules are currently placeholders, so framework-managed CSV/JSON output is not available yet.
- **Analysis (`telemetry/analysis.py`)** provides callable functions for flight and power metrics, GPS distance, turn and stall metrics, endurance estimates, anomaly findings, and flight-summary, GPS-track, and power-usage plots.

### What the framework produces

- **Validated records:** standardized `TelemetryRecord` objects with timestamps, GPS position, altitude, air/ground/vertical speed, heading and attitude, throttle, battery percentage, and optional battery voltage/current/motor power.
- **Flight metrics:** climb rate, flight-path angle, turn rate, distance, battery drain, turn radius and coordination, wind-speed estimate, stall margin, GPS distance, and estimated remaining endurance.
- **Power metrics:** when voltage and current are available, per-sample motor power, average power in watts, and estimated energy used in watt-hours. If power telemetry is missing, these metrics are reported as unavailable.
- **Anomaly findings:** `detect_anomalies()` returns messages for conditions such as excessive roll or pitch, high climb/descent rate, or a large battery drop. It does not display warnings automatically.
- **Plots:** flight-summary, GPS-track, and power-usage charts. Plot functions display a chart or save it to a caller-provided `save_path`.

The framework is not yet wired end to end into `main.py`: the simulator's `L` key still writes its existing CSV format to `flight_logs/`. The `screenshots/` folder contains manually captured simulator images and is unrelated to telemetry output. Analysis plots are displayed or saved to the path supplied by the caller.

## Project files

```text
.
├── .gitignore
├── main.py
├── requirements.txt
├── screenshots/
│   ├── Screenshot 2026-10-09 135903.png
│   ├── Screenshot 2026-10-24 182951.png
│   ├── Screenshot 2026-10-24 183034.png
│   ├── Screenshot 2026-10-24 183355.png
│   ├── Screenshot 2026-10-28 170204.png
│   └── Screenshot 2026-10-28 170252.png
├── simulator/
│   ├── maps/
│   │   ├── coordinates.py
│   │   ├── map.osm
│   │   ├── map_renderer.py
│   │   └── osm_loader.py
│   └── weather.py
├── telemetry/
│   ├── analysis.py
│   ├── pipeline.py
│   ├── processors.py
│   ├── schema.py
│   ├── session.py
│   ├── sinks/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── csv_sink.py
│   │   └── json_sink.py
│   └── sources.py
├── flight_logs/
│   └── flight_log_20261011_134443.csv
└── README.md
```

- `main.py` runs the Pygame/OpenGL flight simulator and connects the aircraft, map, weather, and CSV logging.
- `simulator/maps/` contains the local OpenStreetMap data, coordinate conversion, map loading, and map rendering.
- `simulator/weather.py` implements wind, gust, rain, and atmosphere effects.
- `telemetry/` contains the developing source, processing, validation/schema, session, sink, and analysis modules. The session and sink path is not yet integrated end to end.
- `screenshots/` contains README images, and `flight_logs/` stores recorded CSV flights.
- `.venv/`, Python bytecode, and the downloaded `map_cache/` are local/generated data and are excluded from Git.
