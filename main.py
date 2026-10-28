import csv
import math
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from simulator.weather import WeatherModel
from simulator.maps.coordinates import LocalCoordinates
from simulator.maps.osm_loader import OSMLoader
from simulator.maps.map_renderer import MapRenderer

import pygame
from pygame.locals import (
    DOUBLEBUF,
    OPENGL,
    QUIT,
    KEYDOWN,
    K_ESCAPE,
    K_r,
    K_SPACE,
    K_l,
)

from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_LINES,
    GL_MODELVIEW,
    GL_PROJECTION,
    GL_QUADS,
    GL_TRIANGLES,
    glBegin,
    glClear,
    glClearColor,
    glColor3f,
    glEnable,
    glEnd,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glPopMatrix,
    glPushMatrix,
    glRotatef,
    glTranslatef,
    glVertex3f,
    glViewport,
)
from OpenGL.GLU import gluLookAt, gluPerspective


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(current, target, rate, dt):
    factor = clamp(rate * dt, 0.0, 1.0)
    return current + (target - current) * factor


def wrap_angle(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


# ------------------------------------------------------------
# Fixed-wing aircraft state
# ------------------------------------------------------------

@dataclass
class DroneState:
    x: float = 0.0
    y: float = 35.0
    z: float = 0.0

    roll: float = 0.0
    pitch: float = 0.06
    yaw: float = 0.0

    speed: float = 28.0
    throttle: float = 0.58

    paused: bool = False


class FixedWingDrone:
    """A simplified, illustrative fixed-wing flight model."""

    def __init__(self):
        self.state = DroneState()

    def reset(self):
        self.state = DroneState()

    def update(self, keys, dt, weather):
        s = self.state

        if s.paused:
            return

        roll_input = 0.0
        pitch_input = 0.0
        yaw_input = 0.0

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            roll_input -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            roll_input += 1.0

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            pitch_input += 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            pitch_input -= 1.0

        if keys[pygame.K_q]:
            yaw_input -= 1.0
        if keys[pygame.K_e]:
            yaw_input += 1.0

        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            s.throttle += 0.30 * dt
        if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
            s.throttle -= 0.30 * dt

        s.throttle = clamp(s.throttle, 0.0, 1.0)

        max_roll = math.radians(55.0)
        max_pitch = math.radians(25.0)

        target_roll = roll_input * max_roll
        target_pitch = math.radians(5.0) + pitch_input * max_pitch

        s.roll = lerp(s.roll, target_roll, 3.5, dt)
        s.pitch = lerp(s.pitch, target_pitch, 2.2, dt)

        minimum_speed = 10.0
        maximum_speed = 52.0
        target_speed = minimum_speed + s.throttle * (
            maximum_speed - minimum_speed
        )

        drag = (
            0.25
            + 0.55 * abs(math.sin(s.roll))
            + 0.25 * abs(math.sin(s.pitch))
        )

        acceleration = 5.0 * (target_speed - s.speed) - drag * 4.0
        s.speed += acceleration * dt
        s.speed = clamp(s.speed, 5.0, maximum_speed)

        gravity = 9.81
        turn_rate = gravity * math.tan(s.roll) / max(s.speed, 1.0)
        rudder_rate = yaw_input * math.radians(25.0)

        s.yaw = wrap_angle(s.yaw + (turn_rate + rudder_rate) * dt)

        vertical_speed = s.speed * math.sin(s.pitch)
        vertical_speed -= 1.5 * math.sin(
            s.pitch - math.radians(4.0)
        )

        horizontal_speed = s.speed * math.cos(s.pitch)

        air_velocity_x = horizontal_speed * math.sin(s.yaw)
        air_velocity_z = horizontal_speed * math.cos(s.yaw)

        wind_x, wind_y, wind_z = weather.wind_vector()

        s.x += (air_velocity_x + wind_x) * dt
        s.y += (vertical_speed + wind_y) * dt
        s.z += (air_velocity_z + wind_z) * dt

        if s.y < 2.0:
            s.y = 2.0
            s.pitch = max(s.pitch, math.radians(3.0))
            s.speed *= 0.98


# ------------------------------------------------------------
# OpenGL renderer
# ------------------------------------------------------------

class Renderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        glViewport(0, 0, width, height)
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.42, 0.70, 0.95, 1.0)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(70.0, width / float(height), 0.1, 3000.0)
        glMatrixMode(GL_MODELVIEW)

    def begin_frame(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def set_camera(self, drone):
        s = drone.state

        camera_distance = 18.0
        camera_height = 8.0

        forward_x = math.sin(s.yaw)
        forward_z = math.cos(s.yaw)

        camera_x = s.x - camera_distance * forward_x
        camera_y = s.y + camera_height
        camera_z = s.z - camera_distance * forward_z

        target_x = s.x + 15.0 * forward_x
        target_y = s.y
        target_z = s.z + 15.0 * forward_z

        gluLookAt(
            camera_x, camera_y, camera_z,
            target_x, target_y, target_z,
            0.0, 1.0, 0.0,
        )

    def draw_scene(self, drone):
        self.draw_ground(drone)
        self.draw_drone(drone)

    def draw_ground(self, drone):
        s = drone.state
        grid_spacing = 20.0
        grid_radius = 500.0

        glColor3f(0.15, 0.36, 0.16)
        glBegin(GL_QUADS)
        glVertex3f(s.x - grid_radius, 0.0, s.z - grid_radius)
        glVertex3f(s.x + grid_radius, 0.0, s.z - grid_radius)
        glVertex3f(s.x + grid_radius, 0.0, s.z + grid_radius)
        glVertex3f(s.x - grid_radius, 0.0, s.z + grid_radius)
        glEnd()

        glLineWidth(1.0)
        glColor3f(0.28, 0.52, 0.25)

        start_x = math.floor(s.x / grid_spacing) * grid_spacing
        start_z = math.floor(s.z / grid_spacing) * grid_spacing

        glBegin(GL_LINES)

        for i in range(-25, 26):
            x = start_x + i * grid_spacing
            glVertex3f(x, 0.03, s.z - grid_radius)
            glVertex3f(x, 0.03, s.z + grid_radius)

        for i in range(-25, 26):
            z = start_z + i * grid_spacing
            glVertex3f(s.x - grid_radius, 0.03, z)
            glVertex3f(s.x + grid_radius, 0.03, z)

        glEnd()

        glLineWidth(3.0)
        glColor3f(0.85, 0.85, 0.75)
        glBegin(GL_LINES)
        glVertex3f(s.x - 500.0, 0.05, s.z)
        glVertex3f(s.x + 500.0, 0.05, s.z)
        glEnd()

    def draw_drone(self, drone):
        s = drone.state

        glPushMatrix()
        glTranslatef(s.x, s.y, s.z)
        glRotatef(math.degrees(s.yaw), 0.0, 1.0, 0.0)
        glRotatef(-math.degrees(s.pitch), 1.0, 0.0, 0.0)
        glRotatef(math.degrees(s.roll), 0.0, 0.0, 1.0)

        self.draw_aircraft_body()
        self.draw_wings()
        self.draw_tail()
        self.draw_propeller()

        glPopMatrix()

    def draw_aircraft_body(self):
        glColor3f(0.82, 0.84, 0.88)
        glBegin(GL_TRIANGLES)

        glVertex3f(0.0, 0.0, 4.0)
        glVertex3f(-0.65, -0.35, 1.0)
        glVertex3f(0.65, -0.35, 1.0)

        glVertex3f(0.0, 0.0, 4.0)
        glVertex3f(0.65, -0.35, 1.0)
        glVertex3f(0.0, 0.5, 1.0)

        glVertex3f(0.0, 0.0, 4.0)
        glVertex3f(0.0, 0.5, 1.0)
        glVertex3f(-0.65, -0.35, 1.0)

        glVertex3f(-0.65, -0.35, 1.0)
        glVertex3f(0.65, -0.35, 1.0)
        glVertex3f(0.0, -0.35, -3.0)

        glEnd()

        glColor3f(0.20, 0.22, 0.25)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex3f(0.0, 0.05, -2.5)
        glVertex3f(0.0, 0.05, 3.8)
        glEnd()

    def draw_wings(self):
        glColor3f(0.12, 0.25, 0.58)
        glBegin(GL_TRIANGLES)

        glVertex3f(-0.35, 0.0, 1.4)
        glVertex3f(-7.0, 0.0, -0.8)
        glVertex3f(-0.45, 0.0, -1.0)

        glVertex3f(0.35, 0.0, 1.4)
        glVertex3f(7.0, 0.0, -0.8)
        glVertex3f(0.45, 0.0, -1.0)

        glEnd()

        glColor3f(0.92, 0.22, 0.10)
        glBegin(GL_TRIANGLES)

        glVertex3f(-6.2, 0.0, -0.55)
        glVertex3f(-7.0, 0.0, -0.8)
        glVertex3f(-6.1, 0.0, -1.05)

        glVertex3f(6.2, 0.0, -0.55)
        glVertex3f(7.0, 0.0, -0.8)
        glVertex3f(6.1, 0.0, -1.05)

        glEnd()

    def draw_tail(self):
        glColor3f(0.15, 0.28, 0.62)
        glBegin(GL_TRIANGLES)

        glVertex3f(-0.2, 0.0, -2.1)
        glVertex3f(-3.0, 0.0, -3.0)
        glVertex3f(-0.25, 0.0, -3.3)

        glVertex3f(0.2, 0.0, -2.1)
        glVertex3f(3.0, 0.0, -3.0)
        glVertex3f(0.25, 0.0, -3.3)

        glEnd()

        glColor3f(0.10, 0.20, 0.50)
        glBegin(GL_TRIANGLES)
        glVertex3f(0.0, 0.0, -2.0)
        glVertex3f(0.0, 2.0, -3.1)
        glVertex3f(0.0, 0.0, -3.5)
        glEnd()

    def draw_propeller(self):
        glColor3f(0.08, 0.08, 0.08)
        glLineWidth(3.0)
        glBegin(GL_LINES)
        glVertex3f(-1.5, 0.0, 3.8)
        glVertex3f(1.5, 0.0, 3.8)
        glVertex3f(0.0, -1.5, 3.8)
        glVertex3f(0.0, 1.5, 3.8)
        glEnd()


# ------------------------------------------------------------
# CSV logging
# ------------------------------------------------------------

CSV_FIELDS = [
    "time_s",
    "x_m",
    "altitude_m",
    "z_m",
    "speed_mps",
    "throttle_percent",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "paused",
]


def create_log_file():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"flight_log_{timestamp}.csv"
    log_directory = Path(__file__).resolve().parent / "flight_logs"
    log_directory.mkdir(exist_ok=True)
    filepath = log_directory / filename

    csv_file = open(filepath, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    writer.writeheader()
    csv_file.flush()

    return csv_file, writer, filepath


def log_telemetry(writer, csv_file, sim_time, state):
    writer.writerow({
        "time_s": f"{sim_time:.3f}",
        "x_m": f"{state.x:.3f}",
        "altitude_m": f"{state.y:.3f}",
        "z_m": f"{state.z:.3f}",
        "speed_mps": f"{state.speed:.3f}",
        "throttle_percent": f"{state.throttle * 100.0:.2f}",
        "roll_deg": f"{math.degrees(state.roll):.3f}",
        "pitch_deg": f"{math.degrees(state.pitch):.3f}",
        "yaw_deg": f"{math.degrees(state.yaw):.3f}",
        "paused": state.paused,
    })

    # Flush each row so recent samples are saved while the program runs.
    csv_file.flush()


# ------------------------------------------------------------
# Main application
# ------------------------------------------------------------

def main():
    pygame.init()

    width = 1280
    height = 720

    pygame.display.set_caption("Fixed-Wing Drone Simulator")
    pygame.display.set_mode(
        (width, height),
        OPENGL | DOUBLEBUF,
        vsync=1,
    )

    clock = pygame.time.Clock()
    drone = FixedWingDrone()
    renderer = Renderer(width, height)

    # Replace these with your chosen flight-area coordinates.
    HOME_LAT = 50.683
    HOME_LON = 10.919

    coordinates = LocalCoordinates(HOME_LAT, HOME_LON)

    project_root = Path(__file__).resolve().parent
    osm_file = project_root / "simulator" / "maps" / "map.osm"

    loader = OSMLoader(
        coordinates=coordinates,
        cache_dir=project_root / "map_cache",
    )

    osm_renderer = None
    try:
        if osm_file.is_file():
            print(f"Loading local OpenStreetMap data: {osm_file}")

        map_data = loader.load(
            half_size_m=600.0,
            offline=False,
            refresh=False,
            osm_file=osm_file if osm_file.is_file() else None,
        )
        osm_renderer = MapRenderer(map_data)
    except (OSError, RuntimeError) as exc:
        print(
            f"Warning: OSM map unavailable: {exc}\n"
            "The simulator will continue without map features. "
            "Run again when the map service is available to cache the map."
        )

    weather = WeatherModel(seed=42)

    print(
    "Weather: F1 calm | F2 windy | F3 rain | F4 heavy rain\n"
    "1/2 wind speed | 3/4 rain | 5/6 direction | 7/8 gusts"
    )

    csv_file = None
    csv_writer = None
    csv_path = None
    last_saved_csv_path = None
    recording = False

    sim_time = 0.0
    log_interval = 0.1  # 10 samples per simulated second
    log_timer = 0.0
    running = True

    try:
        while running:
            dt = min(clock.tick(60) / 1000.0, 0.05)

            for event in pygame.event.get():
                if weather.handle_event(event):
                    print(weather.summary())

                if event.type == QUIT:
                    running = False

                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        running = False

                    elif event.key == K_r:
                        drone.reset()
                        weather.reset_particle_anchor(
                            (drone.state.x, drone.state.y, drone.state.z)
                        )

                    elif event.key == K_SPACE:
                        drone.state.paused = not drone.state.paused

                    elif event.key == K_l:
                        recording = not recording

                        if recording:
                            csv_file, csv_writer, csv_path = create_log_file()
                            last_saved_csv_path = csv_path
                            log_timer = 0.0

                            log_telemetry(csv_writer, csv_file, sim_time, drone.state)

                            print(f"Recording started: {csv_path}")

                        else:
                            if csv_file is not None:
                                csv_file.close()
                                print(f"Recording stopped: Telemetry saved {csv_path}")

                            csv_file = None
                            csv_writer = None
                            csv_path = None
                            log_timer = 0.0

            keys = pygame.key.get_pressed()
            weather_dt = 0.0 if drone.state.paused else dt

            weather.update(weather_dt)
            drone.update(keys, dt, weather)

            s = drone.state
            weather.update_particles(
                weather_dt,
                (s.x, s.y, s.z),
            )

            if not drone.state.paused:
                sim_time += dt
                if recording:
                    log_timer += dt

            if recording and log_timer >= log_interval:
                log_telemetry(csv_writer, csv_file, sim_time, drone.state)
                log_timer = 0.0

            weather.apply_atmosphere()

            renderer.begin_frame()
            renderer.set_camera(drone)
            renderer.draw_ground(drone)
            if osm_renderer is not None:
                osm_renderer.draw()
            renderer.draw_drone(drone)

            s = drone.state
            weather.draw_rain((s.x, s.y, s.z))
            if osm_renderer is not None:
                osm_renderer.draw_attribution()

            recording_status = "REC" if recording else "NOT RECORDING"
            pygame.display.set_caption(
                f"Fixed-Wing UAV | "
                f"Speed {s.speed:.1f} m/s | "
                f"Altitude {s.y:.1f} m | "
                f"{recording_status} | "
                f"L: Start/Stop CSV"
            )

            pygame.display.flip()

    finally:
        if csv_file is not None:
            csv_file.close()

            if csv_path is not None:
                print(f"Recording stopped. Telemetry saved to: {csv_path}")

        pygame.quit()
        if last_saved_csv_path is not None:
            print(f"Last CSV log: {last_saved_csv_path}")

    sys.exit()


if __name__ == "__main__":
    main()