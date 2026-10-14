"""
Weather for the existing PyGame/PyOpenGL fixed-wing simulator.

World coordinates:
    +X = east
    +Y = up
    +Z = north

Wind direction uses the meteorological "from" convention:
    0 degrees   = from north, toward south
    90 degrees  = from east, toward west
    180 degrees = from south, toward north
    270 degrees = from west, toward east

Controls:
    F1: calm
    F2: windy
    F3: rain with wind
    F4: heavy rain with stronger wind

    1 / 2: decrease / increase wind speed
    3 / 4: decrease / increase rain rate
    5 / 6: rotate wind direction
    7 / 8: decrease / increase gust strength

This module does not move the aircraft itself.
main.py must apply wind_vector() during the aircraft position update.
"""

import math
import random
from dataclasses import dataclass

import pygame
from OpenGL import GL


def clamp(value, lower, upper):
    return max(lower, min(upper, value))

@dataclass
class WeatherState:
    wind_speed_mps: float = 0.0
    wind_from_deg: float = 270.0

    # Standard deviation of each horizontal gust component.
    gust_strength_mps: float = 0.0
    gust_time_constant_s: float = 2.0

    rain_rate_mmph: float = 0.0

    # Used when rain is absent; rain reduces the displayed visibility.
    clear_visibility_m: float = 3000.0

class WeatherModel:
    MAX_WIND_MPS = 30.0
    MAX_GUST_MPS = 12.0
    MAX_RAIN_MMPH = 50.0

    def __init__(self, state=None, seed=42, max_particles=1200):
        self.state = state if state is not None else WeatherState()

        # Separate random streams: rendering does not change wind randomness.
        self._wind_rng = random.Random(seed)
        self._rain_rng = random.Random(seed + 1)

        self._gust_x = 0.0
        self._gust_z = 0.0

        self._radius = 65.0
        self._height = 55.0

        # Particle offsets relative to an anchor near the aircraft.
        self._particles = [
            [
                self._rain_rng.uniform(-self._radius, self._radius),
                self._rain_rng.uniform(-self._height, self._height),
                self._rain_rng.uniform(-self._radius, self._radius),
            ]
            for _ in range(max_particles)
        ]

        self._previous_anchor = None
        self._validate()

    def _validate(self):
        s = self.state

        s.wind_speed_mps = clamp(
            s.wind_speed_mps, 0.0, self.MAX_WIND_MPS
        )
        s.wind_from_deg %= 360.0

        s.gust_strength_mps = clamp(
            s.gust_strength_mps, 0.0, self.MAX_GUST_MPS
        )
        s.gust_time_constant_s = max(0.1, s.gust_time_constant_s)

        s.rain_rate_mmph = clamp(
            s.rain_rate_mmph, 0.0, self.MAX_RAIN_MMPH
        )
        s.clear_visibility_m = max(100.0, s.clear_visibility_m)

    def set_preset(self, name):
        """
        Presets are illustrative scenario settings, not official
        meteorological classifications.
        """
        presets = {
            "calm": (0.0, 0.0, 0.0),
            "windy": (8.0, 2.0, 0.0),
            "rain": (6.0, 1.5, 6.0),
            "heavy_rain": (14.0, 4.0, 25.0),
        }

        if name not in presets:
            raise ValueError(f"Unknown weather preset: {name}")

        wind, gust, rain = presets[name]

        self.state.wind_speed_mps = wind
        self.state.gust_strength_mps = gust
        self.state.rain_rate_mmph = rain

        self._gust_x = 0.0
        self._gust_z = 0.0

        self._validate()

    def handle_event(self, event):
        """Call once for every event retrieved by main.py."""
        if event.type != pygame.KEYDOWN:
            return False

        key = event.key

        if key == pygame.K_F1:
            self.set_preset("calm")
        elif key == pygame.K_F2:
            self.set_preset("windy")
        elif key == pygame.K_F3:
            self.set_preset("rain")
        elif key == pygame.K_F4:
            self.set_preset("heavy_rain")

        elif key == pygame.K_1:
            self.state.wind_speed_mps -= 1.0
        elif key == pygame.K_2:
            self.state.wind_speed_mps += 1.0

        elif key == pygame.K_3:
            self.state.rain_rate_mmph -= 1.0
        elif key == pygame.K_4:
            self.state.rain_rate_mmph += 1.0

        elif key == pygame.K_5:
            self.state.wind_from_deg -= 15.0
        elif key == pygame.K_6:
            self.state.wind_from_deg += 15.0

        elif key == pygame.K_7:
            self.state.gust_strength_mps -= 0.5
        elif key == pygame.K_8:
            self.state.gust_strength_mps += 0.5

        else:
            return False

        self._validate()

        # Explicitly removing gusts should remove any residual gust.
        if self.state.gust_strength_mps == 0.0:
            self._gust_x = 0.0
            self._gust_z = 0.0

        return True
    
    def update(self, dt):
        """Advance the wind model once per unpaused simulation frame."""
        if dt <= 0.0:
            return

        self._validate()

        strength = self.state.gust_strength_mps

        if strength == 0.0:
            self._gust_x = 0.0
            self._gust_z = 0.0
            return

        # Correlated stochastic gusts with a finite correlation time.
        decay = math.exp(-dt / self.state.gust_time_constant_s)
        noise_scale = strength * math.sqrt(
            max(0.0, 1.0 - decay * decay)
        )

        self._gust_x = (
            decay * self._gust_x
            + noise_scale * self._wind_rng.gauss(0.0, 1.0)
        )
        self._gust_z = (
            decay * self._gust_z
            + noise_scale * self._wind_rng.gauss(0.0, 1.0)
        )

    def wind_vector(self):
        """Return the current world-frame wind velocity in m/s."""
        #s = self.state

        # Convert meteorological "from" direction to mathematical "to" direction.
        direction = math.radians(self.state.wind_from_deg)

        wind_x = -self.state.wind_speed_mps * math.sin(direction)
        wind_z = -self.state.wind_speed_mps * math.cos(direction)

        return (
            wind_x + self._gust_x,
            0.0,
            wind_z + self._gust_z,
        )

    def update_particles(self, dt, anchor):
        """Update the rain particle positions relative to the anchor point.

        The anchor is typically the aircraft position, but it can be any
        world coordinate.  The particles are not affected by wind; they
        fall straight down in world coordinates.
        """
        anchor = tuple(anchor)

        if self._previous_anchor is None:
            self._previous_anchor = anchor

        delta = tuple(
            current - previous
            for current, previous in zip(
                anchor, self._previous_anchor
            )
        )
        self._previous_anchor = anchor

        wind_x, _, wind_z = self.wind_vector()

        # Illustrative falling speed, not a drop-size model.
        fall_speed = 18.0
        width = 2.0 * self._radius
        height = 2.0 * self._height

        for particle in self._particles:
            particle[0] += wind_x * dt - delta[0]
            particle[1] += -fall_speed * dt - delta[1]
            particle[2] += wind_z * dt - delta[2]

            particle[0] = (
                (particle[0] + self._radius) % width
                - self._radius
            )
            particle[1] = (
                (particle[1] + self._height) % height
                - self._height
            )
            particle[2] = (
                (particle[2] + self._radius) % width
                - self._radius
            )
    
    def reset_particle_anchor(self, anchor):
        """Reset the particle anchor to the given world coordinate."""
        self._previous_anchor = tuple(anchor)

    def visibibility_m(self):
        """Return the current visibility in meters."""
        # Illustrative model: rain reduces visibility, but it cannot
        # exceed the clear visibility.
        return max(
            120.0,
            self.state.clear_visibility_m / (1.0 + 0.15 * self.state.rain_rate_mmph),
        )

    def sky_color(self):
        amount = clamp(self.state.rain_rate_mmph / 25.0, 0.0, 1.0)

        clear = (0.42, 0.70, 0.95)
        rainy = (0.26, 0.30, 0.36)

        return tuple(
            a + (b - a) * amount
            for a, b in zip(clear, rainy)
        )

    def apply_atmosphere(self):
        """
        Call BEFORE renderer.begin_frame() so glClear uses this sky.

        Uses compatibility-profile OpenGL, matching the existing renderer.
        """
        color = self.sky_color()
        GL.glClearColor(*color, 1.0)

        if self.state.rain_rate_mmph <= 0.0:
            GL.glDisable(GL.GL_FOG)
            return

        GL.glEnable(GL.GL_FOG)
        GL.glFogi(GL.GL_FOG_MODE, GL.GL_LINEAR)
        GL.glFogfv(GL.GL_FOG_COLOR, (*color, 1.0))
        GL.glFogf(GL.GL_FOG_START, 20.0)
        GL.glFogf(GL.GL_FOG_END, self.visibility_m())

    def draw_rain(self, anchor):
        """
        Call after drawing the scene, with its camera matrix still active.
        """
        rain = self.state.rain_rate_mmph

        if rain <= 0.0:
            return

        count = min(
            len(self._particles),
            max(1, int(rain * 40)),
        )

        ax, ay, az = anchor
        wind_x, _, wind_z = self.wind_vector()

        # A short world-space streak along the drop's velocity.
        exposure_s = 0.07
        dx = wind_x * exposure_s
        dy = -18.0 * exposure_s
        dz = wind_z * exposure_s

        GL.glPushAttrib(GL.GL_ALL_ATTRIB_BITS)

        try:
            GL.glDisable(GL.GL_LIGHTING)
            GL.glDisable(GL.GL_TEXTURE_2D)

            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glDepthMask(GL.GL_FALSE)

            GL.glEnable(GL.GL_BLEND)
            GL.glBlendFunc(
                GL.GL_SRC_ALPHA,
                GL.GL_ONE_MINUS_SRC_ALPHA,
            )

            GL.glLineWidth(1.0)
            GL.glColor4f(0.75, 0.85, 1.0, 0.55)

            GL.glBegin(GL.GL_LINES)

            for i in range(count):
                px, py, pz = self._particles[i]

                x = ax + px
                y = ay + py
                z = az + pz

                if y < 0.1:
                    continue

                GL.glVertex3f(x, y, z)
                GL.glVertex3f(x + dx, max(0.1, y + dy), z + dz)

            GL.glEnd()

        finally:
            GL.glPopAttrib()

    def telemetry(self):
        """Additional values available for CSV logging."""
        wx, wy, wz = self.wind_vector()

        return {
            "wind_x_mps": wx,
            "wind_y_mps": wy,
            "wind_z_mps": wz,
            "wind_base_speed_mps": self.state.wind_speed_mps,
            "wind_from_deg": self.state.wind_from_deg,
            "gust_strength_mps": self.state.gust_strength_mps,
            "rain_rate_mmph": self.state.rain_rate_mmph,
            "visibility_m": self.visibility_m(),
        }

    def summary(self):
        return (
            f"Wind {self.state.wind_speed_mps:.1f} m/s "
            f"from {self.state.wind_from_deg:.0f} deg | "
            f"Rain {self.state.rain_rate_mmph:.1f} mm/h"
        )