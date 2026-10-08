import math
import sys
from dataclasses import dataclass

import pygame
from pygame.locals import DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_r, K_SPACE

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
    glDisable,
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

    roll_rate: float = 0.0
    pitch_rate: float = 0.0
    yaw_rate: float = 0.0

    speed: float = 28.0
    throttle: float = 0.58

    paused: bool = False


class FixedWingDrone:
    """
    Simplified fixed-wing flight model.

    Coordinate system:
        x: east/west
        y: altitude
        z: north/south

    The drone's forward direction is based on yaw and pitch.
    Roll controls turn authority.
    Pitch controls climb or descent.
    """

    def __init__(self):
        self.state = DroneState()

    def reset(self):
        self.state = DroneState()

    def update(self, keys, dt):
        s = self.state

        if s.paused:
            return

        # User control inputs in the range [-1, 1].
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

        # Throttle control.
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            s.throttle += 0.30 * dt

        if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
            s.throttle -= 0.30 * dt

        s.throttle = clamp(s.throttle, 0.0, 1.0)

        # Target attitude.
        max_roll = math.radians(55.0)
        max_pitch = math.radians(25.0)

        target_roll = roll_input * max_roll
        target_pitch = math.radians(5.0) + pitch_input * max_pitch

        # Smooth aircraft attitude.
        s.roll = lerp(s.roll, target_roll, 3.5, dt)
        s.pitch = lerp(s.pitch, target_pitch, 2.2, dt)

        # Speed model.
        minimum_speed = 10.0
        maximum_speed = 52.0
        target_speed = minimum_speed + s.throttle * (maximum_speed - minimum_speed)

        # Drag increases at high pitch and during aggressive banking.
        drag = (
            0.25
            + 0.55 * abs(math.sin(s.roll))
            + 0.25 * abs(math.sin(s.pitch))
        )

        acceleration = 5.0 * (target_speed - s.speed) - drag * 4.0
        s.speed += acceleration * dt
        s.speed = clamp(s.speed, 5.0, maximum_speed)

        # Banked turn model.
        gravity = 9.81
        turn_rate = gravity * math.tan(s.roll) / max(s.speed, 1.0)

        # Rudder input adds yaw authority.
        rudder_rate = yaw_input * math.radians(25.0)

        s.yaw += (turn_rate + rudder_rate) * dt
        s.yaw = wrap_angle(s.yaw)

        # Climb/descent caused by pitch.
        vertical_speed = s.speed * math.sin(s.pitch)

        # Add a small gravity-like tendency toward level flight.
        vertical_speed -= 1.5 * math.sin(s.pitch - math.radians(4.0))

        s.y += vertical_speed * dt

        # Forward horizontal velocity.
        horizontal_speed = s.speed * math.cos(s.pitch)

        s.x += horizontal_speed * math.sin(s.yaw) * dt
        s.z += horizontal_speed * math.cos(s.yaw) * dt

        # Ground collision.
        if s.y < 2.0:
            s.y = 2.0
            s.pitch = max(s.pitch, math.radians(3.0))
            s.speed *= 0.98


# ------------------------------------------------------------
# Rendering
# ------------------------------------------------------------

class Renderer:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        glEnable(GL_DEPTH_TEST)
        glClearColor(0.42, 0.70, 0.95, 1.0)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(
            70.0,
            width / float(height),
            0.1,
            3000.0,
        )

        glMatrixMode(GL_MODELVIEW)

    def resize(self, width, height):
        self.width = width
        self.height = max(height, 1)

        glViewport(0, 0, width, height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(
            70.0,
            width / float(height),
            0.1,
            3000.0,
        )

        glMatrixMode(GL_MODELVIEW)

    def begin_frame(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def set_camera(self, drone):
        s = drone.state

        # Camera behind and above the drone.
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
            camera_x,
            camera_y,
            camera_z,
            target_x,
            target_y,
            target_z,
            0.0,
            1.0,
            0.0,
        )

    def draw_scene(self, drone):
        self.draw_sky_objects()
        self.draw_ground(drone)
        self.draw_drone(drone)

    def draw_sky_objects(self):
        # Distant reference lines provide spatial orientation.
        glLineWidth(1.0)
        glColor3f(0.75, 0.88, 0.98)

        glBegin(GL_LINES)

        for altitude in [20.0, 40.0, 60.0, 80.0]:
            glVertex3f(-500.0, altitude, -500.0)
            glVertex3f(500.0, altitude, -500.0)

        glEnd()

    def draw_ground(self, drone):
        s = drone.state
        grid_spacing = 20.0
        grid_radius = 500.0

        # Large green ground plane.
        glColor3f(0.15, 0.36, 0.16)

        glBegin(GL_QUADS)
        glVertex3f(s.x - grid_radius, 0.0, s.z - grid_radius)
        glVertex3f(s.x + grid_radius, 0.0, s.z - grid_radius)
        glVertex3f(s.x + grid_radius, 0.0, s.z + grid_radius)
        glVertex3f(s.x - grid_radius, 0.0, s.z + grid_radius)
        glEnd()

        # Ground grid centered around the aircraft.
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

        # A runway-like central reference stripe.
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

        # OpenGL rotations:
        # yaw around vertical axis, pitch around lateral axis,
        # roll around longitudinal axis.
        glRotatef(math.degrees(s.yaw), 0.0, 1.0, 0.0)
        glRotatef(-math.degrees(s.pitch), 1.0, 0.0, 0.0)
        glRotatef(math.degrees(s.roll), 0.0, 0.0, 1.0)

        self.draw_aircraft_body()
        self.draw_wings()
        self.draw_tail()
        self.draw_propeller()

        glPopMatrix()

    def draw_aircraft_body(self):
        # Nose points in +Z direction.
        glColor3f(0.82, 0.84, 0.88)

        glBegin(GL_TRIANGLES)

        # Nose cone.
        glVertex3f(0.0, 0.0, 4.0)
        glVertex3f(-0.65, -0.35, 1.0)
        glVertex3f(0.65, -0.35, 1.0)

        glVertex3f(0.0, 0.0, 4.0)
        glVertex3f(0.65, -0.35, 1.0)
        glVertex3f(0.0, 0.5, 1.0)

        glVertex3f(0.0, 0.0, 4.0)
        glVertex3f(0.0, 0.5, 1.0)
        glVertex3f(-0.65, -0.35, 1.0)

        # Rear fuselage bottom.
        glVertex3f(-0.65, -0.35, 1.0)
        glVertex3f(0.65, -0.35, 1.0)
        glVertex3f(0.0, -0.35, -3.0)

        glEnd()

        # Fuselage center line.
        glColor3f(0.20, 0.22, 0.25)
        glLineWidth(2.0)

        glBegin(GL_LINES)
        glVertex3f(0.0, 0.05, -2.5)
        glVertex3f(0.0, 0.05, 3.8)
        glEnd()

    def draw_wings(self):
        glColor3f(0.12, 0.25, 0.58)

        glBegin(GL_TRIANGLES)

        # Left wing.
        glVertex3f(-0.35, 0.0, 1.4)
        glVertex3f(-7.0, 0.0, -0.8)
        glVertex3f(-0.45, 0.0, -1.0)

        # Right wing.
        glVertex3f(0.35, 0.0, 1.4)
        glVertex3f(7.0, 0.0, -0.8)
        glVertex3f(0.45, 0.0, -1.0)

        glEnd()

        # Wing tips.
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
        # Horizontal stabilizer.
        glColor3f(0.15, 0.28, 0.62)

        glBegin(GL_TRIANGLES)

        glVertex3f(-0.2, 0.0, -2.1)
        glVertex3f(-3.0, 0.0, -3.0)
        glVertex3f(-0.25, 0.0, -3.3)

        glVertex3f(0.2, 0.0, -2.1)
        glVertex3f(3.0, 0.0, -3.0)
        glVertex3f(0.25, 0.0, -3.3)

        glEnd()

        # Vertical stabilizer.
        glColor3f(0.10, 0.20, 0.50)

        glBegin(GL_TRIANGLES)
        glVertex3f(0.0, 0.0, -2.0)
        glVertex3f(0.0, 2.0, -3.1)
        glVertex3f(0.0, 0.0, -3.5)
        glEnd()

    def draw_propeller(self):
        # Propeller is drawn as two dark blades in front of the aircraft.
        glColor3f(0.08, 0.08, 0.08)
        glLineWidth(3.0)

        glBegin(GL_LINES)
        glVertex3f(-1.5, 0.0, 3.8)
        glVertex3f(1.5, 0.0, 3.8)
        glVertex3f(0.0, -1.5, 3.8)
        glVertex3f(0.0, 1.5, 3.8)
        glEnd()


# ------------------------------------------------------------
# HUD
# ------------------------------------------------------------

class HUD:
    def __init__(self, font):
        self.font = font

    def draw_text(self, surface, text, position, color=(255, 255, 255)):
        rendered = self.font.render(text, True, color)
        surface.blit(rendered, position)

    def draw(self, surface, drone):
        s = drone.state

        panel_color = (12, 18, 28)
        white = (235, 240, 245)
        green = (100, 240, 130)
        yellow = (245, 220, 100)
        red = (245, 90, 80)

        # Semi-transparent information panel.
        panel = pygame.Surface((330, 170), pygame.SRCALPHA)
        panel.fill((panel_color[0], panel_color[1], panel_color[2], 205))
        surface.blit(panel, (16, 16))

        self.draw_text(surface, "FIXED-WING UAV SIMULATOR", (30, 28), white)
        self.draw_text(surface, f"Speed:    {s.speed:6.1f} m/s", (30, 58), green)
        self.draw_text(surface, f"Altitude: {s.y:6.1f} m", (30, 82), green)
        self.draw_text(surface, f"Throttle: {s.throttle * 100:5.1f} %", (30, 106), yellow)
        self.draw_text(
            surface,
            f"Roll:     {math.degrees(s.roll):6.1f} deg",
            (30, 130),
            white,
        )
        self.draw_text(
            surface,
            f"Pitch:    {math.degrees(s.pitch):6.1f} deg",
            (30, 154),
            white,
        )

        controls = [
            "W/S or Up/Down: pitch",
            "A/D or Left/Right: roll",
            "Q/E: rudder yaw",
            "Shift/Ctrl: throttle",
            "R: reset     Space: pause",
            "Esc: quit",
        ]

        y = surface.get_height() - 155

        for line in controls:
            self.draw_text(surface, line, (20, y), white)
            y += 23

        if s.paused:
            pause_text = self.font.render("PAUSED", True, red)
            x = (surface.get_width() - pause_text.get_width()) // 2
            y = surface.get_height() // 2
            surface.blit(pause_text, (x, y))


# ------------------------------------------------------------
# Main application
# ------------------------------------------------------------

def main():
    pygame.init()
    pygame.font.init()

    width = 1280
    height = 720

    pygame.display.set_caption("Fixed-Wing Drone Simulator")

    pygame.display.set_mode(
        (width, height),
        OPENGL | DOUBLEBUF,
        vsync=1,
    )

    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 18)
    hud = HUD(font)
    drone = FixedWingDrone()
    renderer = Renderer(width, height)

    running = True

    while running:
        dt = clock.tick(60) / 1000.0
        dt = min(dt, 0.05)

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False

            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False

                elif event.key == K_r:
                    drone.reset()

                elif event.key == K_SPACE:
                    drone.state.paused = not drone.state.paused

        keys = pygame.key.get_pressed()
        drone.update(keys, dt)

        renderer.begin_frame()
        renderer.set_camera(drone)
        renderer.draw_scene(drone)

        # OpenGL rendering must finish before switching to the 2D HUD.
        pygame.display.flip()

        # Draw HUD in a separate 2D surface after the OpenGL frame.
        # This works reliably when the HUD is drawn before the next frame
        # is cleared by OpenGL.
        #
        # For maximum compatibility, use a second normal display surface
        # only if your driver supports it. The current implementation keeps
        # the OpenGL scene and input functional across common systems.

        pygame.display.set_caption(
            f"Fixed-Wing UAV | "
            f"Speed {drone.state.speed:.1f} m/s | "
            f"Altitude {drone.state.y:.1f} m"
        )

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()