"""Convert geographic coordinates to the simulator's local metric frame.

Simulator convention:
    x = east
    y = up, handled separately
    z = north

This is a local projected horizontal coordinate system, not a terrain
elevation model or a full 3D ENU transformation.
"""

import math

from pyproj import CRS, Transformer


class LocalCoordinates:
    def __init__(self, origin_lat, origin_lon):
        self.origin_lat = float(origin_lat)
        self.origin_lon = float(origin_lon)

        self._validate(self.origin_lat, self.origin_lon)

        local_crs = CRS.from_proj4(
            f"+proj=aeqd "
            f"+lat_0={self.origin_lat} "
            f"+lon_0={self.origin_lon} "
            f"+datum=WGS84 +units=m +no_defs"
        )

        self._to_local = Transformer.from_crs(
            "EPSG:4326",
            local_crs,
            always_xy=True,
        )

        self._to_geographic = Transformer.from_crs(
            local_crs,
            "EPSG:4326",
            always_xy=True,
        )

    @staticmethod
    def _validate(latitude, longitude):
        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90.0 <= latitude <= 90.0
            and -180.0 <= longitude <= 180.0
        ):
            raise ValueError("Invalid latitude or longitude.")

    def to_local(self, latitude, longitude):
        """Return (x_east_m, z_north_m)."""
        self._validate(latitude, longitude)

        x, z = self._to_local.transform(
            longitude,
            latitude,
            errcheck=True,
        )
        return float(x), float(z)

    def to_geographic(self, x_m, z_m):
        """Return (latitude, longitude)."""
        longitude, latitude = self._to_geographic.transform(
            x_m,
            z_m,
            errcheck=True,
        )
        return float(latitude), float(longitude)

    def bounding_box(self, half_size_m=600.0):
        """Return (south, west, north, east) around the origin.

        Intended for small local areas, away from the poles and
        antimeridian.
        """
        if not 50.0 <= half_size_m <= 2000.0:
            raise ValueError("Use a half-size between 50 and 2000 metres.")

        if abs(self.origin_lat) > 80.0:
            raise ValueError("This example does not support polar areas.")

        points = [
            self.to_geographic(x, z)
            for x in (-half_size_m, 0.0, half_size_m)
            for z in (-half_size_m, 0.0, half_size_m)
        ]

        latitudes = [lat for lat, _ in points]
        longitudes = [lon for _, lon in points]

        if max(longitudes) - min(longitudes) > 180.0:
            raise ValueError("Areas crossing the antimeridian are unsupported.")

        return (
            min(latitudes),
            min(longitudes),
            max(latitudes),
            max(longitudes),
        )