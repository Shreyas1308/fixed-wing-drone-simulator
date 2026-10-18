"""Render simple OSM roads, building walls, and attribution."""

import math

import pygame
from OpenGL import GL

from .osm_loader import building_height


class MapRenderer:
    def __init__(self, map_data):
        self.map_data = map_data

        # Prepare CPU geometry once, not every rendering frame.
        self._road_quads = []
        self._walls = []
        self._roof_edges = []

        self._prepare_geometry()

        if not pygame.font.get_init():
            pygame.font.init()

        font = pygame.font.Font(None, 20)
        label = (
            "© OpenStreetMap contributors | ODbL | "
            "openstreetmap.org/copyright"
        )

        text = font.render(label, True, (245, 245, 245))

        panel = pygame.Surface(
            (text.get_width() + 16, text.get_height() + 12),
            pygame.SRCALPHA,
        )
        panel.fill((12, 18, 25, 225))
        panel.blit(text, (8, 6))

        self._label_size = panel.get_size()
        self._label_pixels = pygame.image.tobytes(
            panel, "RGBA", True
        )

    @staticmethod
    def _road_width(tags):
        road_type = tags.get("highway", "")

        if road_type in {"motorway", "trunk"}:
            return 12.0
        if road_type in {"primary", "secondary"}:
            return 8.0
        if road_type in {"footway", "path", "steps", "cycleway"}:
            return 2.0

        return 5.0

    def _prepare_geometry(self):
        for road in self.map_data.roads:
            half_width = self._road_width(road.tags) / 2.0

            for a, b in zip(road.points, road.points[1:]):
                dx = b[0] - a[0]
                dz = b[1] - a[1]
                length = math.hypot(dx, dz)

                if length < 0.01:
                    continue

                nx = -dz / length * half_width
                nz = dx / length * half_width
                y = 0.08

                self._road_quads.append((
                    (a[0] + nx, y, a[1] + nz),
                    (b[0] + nx, y, b[1] + nz),
                    (b[0] - nx, y, b[1] - nz),
                    (a[0] - nx, y, a[1] - nz),
                ))

        for building in self.map_data.buildings:
            height = building_height(building.tags)

            for a, b in zip(building.points, building.points[1:]):
                self._walls.append((
                    (a[0], 0.1, a[1]),
                    (b[0], 0.1, b[1]),
                    (b[0], height, b[1]),
                    (a[0], height, a[1]),
                ))

                self._roof_edges.append((
                    (a[0], height, a[1]),
                    (b[0], height, b[1]),
                ))

    def draw(self):
        """Call with the simulator camera/modelview matrix active."""
        GL.glPushAttrib(GL.GL_ALL_ATTRIB_BITS)

        try:
            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glDisable(GL.GL_LIGHTING)
            GL.glDisable(GL.GL_TEXTURE_2D)
            GL.glDisable(GL.GL_CULL_FACE)

            GL.glColor3f(0.25, 0.26, 0.28)
            GL.glBegin(GL.GL_QUADS)
            for quad in self._road_quads:
                for vertex in quad:
                    GL.glVertex3f(*vertex)
            GL.glEnd()

            GL.glColor3f(0.65, 0.61, 0.55)
            GL.glBegin(GL.GL_QUADS)
            for wall in self._walls:
                for vertex in wall:
                    GL.glVertex3f(*vertex)
            GL.glEnd()

            GL.glColor3f(0.30, 0.27, 0.24)
            GL.glLineWidth(1.0)
            GL.glBegin(GL.GL_LINES)
            for a, b in self._roof_edges:
                GL.glVertex3f(*a)
                GL.glVertex3f(*b)
            GL.glEnd()

        finally:
            GL.glPopAttrib()

    def draw_attribution(self):
        """Draw a fixed screen-space label before display.flip()."""
        GL.glPushAttrib(GL.GL_ALL_ATTRIB_BITS)
        GL.glPushClientAttrib(GL.GL_CLIENT_PIXEL_STORE_BIT)

        try:
            GL.glDisable(GL.GL_DEPTH_TEST)
            GL.glDisable(GL.GL_FOG)
            GL.glDisable(GL.GL_LIGHTING)
            GL.glDisable(GL.GL_TEXTURE_2D)
            GL.glDisable(GL.GL_ALPHA_TEST)
            GL.glDisable(GL.GL_SCISSOR_TEST)

            GL.glEnable(GL.GL_BLEND)
            GL.glBlendFunc(
                GL.GL_SRC_ALPHA,
                GL.GL_ONE_MINUS_SRC_ALPHA,
            )

            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glPixelZoom(1.0, 1.0)
            GL.glWindowPos2d(10.0, 10.0)

            width, height = self._label_size

            GL.glDrawPixels(
                width,
                height,
                GL.GL_RGBA,
                GL.GL_UNSIGNED_BYTE,
                self._label_pixels,
            )

        finally:
            GL.glPopClientAttrib()
            GL.glPopAttrib()