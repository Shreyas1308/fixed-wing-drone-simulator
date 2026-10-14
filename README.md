# Fixed-Wing Drone Simulator

A small interactive fixed-wing flight simulator built with Python, Pygame, and OpenGL. Fly a simplified aircraft in a 3D scene, adjust its controls in real time, and record flight telemetry to a CSV file for review after the simulation.

> **Note:** This is an illustrative simulator, not a validated flight model. It is intended for experimentation and learning, not real-world flight planning or control.

## Screenshot

![Fixed-Wing Drone Simulator in flight](screenshots/Screenshot%202026-10-09%20135903.png)

## Features

- 3D aircraft and ground rendering with OpenGL
- Keyboard controls for roll, pitch, yaw, and throttle
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

Open a flight log in a spreadsheet application to inspect the data or create plots after the flight. Live plotting is not included.

## Project files

```text
.
├── main.py
├── simulator/
│   └── weather.py
├── requirements.txt
├── README.md
├── screenshots/
│   └── Screenshot 2026-10-09 135903.png
└── flight_logs/
    └── flight_log_YYYYMMDD_HHMMSS.csv
```
