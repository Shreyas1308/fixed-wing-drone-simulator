"""Load OSM XML or a JSON vector area from Overpass and cache JSON."""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from .coordinates import LocalCoordinates


ATTRIBUTION = (
    "© OpenStreetMap contributors | ODbL | "
    "https://www.openstreetmap.org/copyright"
)


@dataclass(frozen=True)
class MapWay:
    osm_id: int
    points: tuple
    tags: dict


@dataclass(frozen=True)
class MapData:
    roads: tuple
    buildings: tuple
    bounds: tuple


def building_height(tags):
    """Return approximate height in metres.

    Supports plain metric heights and values such as '12 m'.
    Missing/unrecognized values fall back to levels or 9 metres.
    """
    raw = str(tags.get("height", "")).strip().lower()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:m)?", raw)

    if match:
        height = float(match.group(1))
        if math.isfinite(height) and height > 0:
            return min(height, 300.0)

    try:
        levels = float(tags.get("building:levels", ""))
        if math.isfinite(levels) and levels > 0:
            return min(levels * 3.0, 300.0)
    except (TypeError, ValueError):
        pass

    return 9.0


class OSMLoader:
    def __init__(
        self,
        coordinates: LocalCoordinates,
        cache_dir,
        endpoint="https://overpass-api.de/api/interpreter",
    ):
        self.coordinates = coordinates
        self.cache_dir = Path(cache_dir)
        self.endpoint = endpoint

    @staticmethod
    def _check_response(data):
        if not isinstance(data, dict):
            raise RuntimeError("OSM response is not a JSON object.")

        if data.get("remark"):
            raise RuntimeError(
                f"Overpass reported an incomplete/error response: "
                f"{data['remark']}"
            )

        if not isinstance(data.get("elements"), list):
            raise RuntimeError("OSM response has no valid elements list.")

    @staticmethod
    def _read_osm_xml(osm_file):
        osm_file = Path(osm_file)
        nodes = {}
        elements = []

        try:
            parser = ET.iterparse(osm_file, events=("start", "end"))
            try:
                event, root = next(parser)
            except StopIteration as exc:
                raise RuntimeError(
                    f"OSM XML file is empty: {osm_file}"
                ) from exc

            if event != "start" or root.tag != "osm":
                raise RuntimeError(
                    f"Not a valid OSM XML document: {osm_file}"
                )

            for event, element in parser:
                if event != "end":
                    continue

                if element.tag == "node":
                    try:
                        nodes[int(element.attrib["id"])] = {
                            "lat": float(element.attrib["lat"]),
                            "lon": float(element.attrib["lon"]),
                        }
                    except (KeyError, ValueError) as exc:
                        raise RuntimeError(
                            f"Invalid node in OSM XML: {osm_file}"
                        ) from exc

                    element.clear()

                elif element.tag == "way":
                    try:
                        way_id = int(element.attrib["id"])
                        refs = [
                            int(node.attrib["ref"])
                            for node in element.findall("nd")
                        ]
                    except (KeyError, ValueError) as exc:
                        raise RuntimeError(
                            f"Invalid way in OSM XML: {osm_file}"
                        ) from exc

                    if len(refs) >= 2 and all(ref in nodes for ref in refs):
                        tags = {
                            tag.attrib["k"]: tag.attrib["v"]
                            for tag in element.findall("tag")
                            if "k" in tag.attrib and "v" in tag.attrib
                        }
                        elements.append({
                            "type": "way",
                            "id": way_id,
                            "geometry": [nodes[ref] for ref in refs],
                            "tags": tags,
                        })

                    element.clear()

        except ET.ParseError as exc:
            raise RuntimeError(
                f"Could not parse OSM XML file: {osm_file}"
            ) from exc

        return {"elements": elements}

    def _build_map_data(self, data, bounds):
        roads = []
        buildings = []

        for element in data["elements"]:
            if element.get("type") != "way":
                continue

            geometry = element.get("geometry", [])

            if len(geometry) < 2:
                continue

            if any(
                not isinstance(point, dict)
                or "lat" not in point
                or "lon" not in point
                for point in geometry
            ):
                continue

            points = tuple(
                self.coordinates.to_local(point["lat"], point["lon"])
                for point in geometry
            )

            tags = dict(element.get("tags", {}))
            way = MapWay(element["id"], points, tags)

            if "building" in tags and tags["building"] != "no":
                if len(points) >= 4 and points[0] == points[-1]:
                    buildings.append(way)

            elif "highway" in tags and tags.get("area") != "yes":
                roads.append(way)

        print(
            f"Map ready: {len(roads)} road/path ways, "
            f"{len(buildings)} building footprints."
        )

        return MapData(
            roads=tuple(roads),
            buildings=tuple(buildings),
            bounds=bounds,
        )

    def load(
        self,
        half_size_m=600.0,
        offline=False,
        refresh=False,
        osm_file=None,
    ):
        bounds = self.coordinates.bounding_box(half_size_m)

        if osm_file is not None:
            data = self._read_osm_xml(osm_file)
            return self._build_map_data(data, bounds)

        bbox_text = ",".join(f"{value:.7f}" for value in bounds)

        query = f"""
[out:json][45];
(
  way["highway"]({bbox_text});
  way["building"]["building"!="no"]({bbox_text});
);
out body geom;
"""

        cache_key = hashlib.sha256(
            query.encode("utf-8")
        ).hexdigest()[:20]

        cache_path = self.cache_dir / f"osm_{cache_key}.json"

        if cache_path.exists() and (offline or not refresh):
            try:
                data = json.loads(
                    cache_path.read_text(encoding="utf-8")
                )
                self._check_response(data)
            except (ValueError, RuntimeError) as exc:
                raise RuntimeError(
                    f"Invalid cache: {cache_path}. "
                    "Remove it and download again."
                ) from exc
        else:
            if offline:
                raise FileNotFoundError(
                    f"No cached map for this area: {cache_path}"
                )

            print("Downloading a small OSM area. Please wait...")

            try:
                response = requests.post(
                    self.endpoint,
                    data={"data": query},
                    headers={
                        "User-Agent": (
                            "FixedWingDroneSimulator/0.1 "
                            "(local educational OSM visualization)"
                        )
                    },
                    timeout=(10, 75),
                )
                response.raise_for_status()
                data = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise RuntimeError(
                    "OSM download failed. The service may be busy or "
                    "unavailable. Try again later; do not retry in the "
                    "rendering loop."
                ) from exc

            self._check_response(data)

            self.cache_dir.mkdir(parents=True, exist_ok=True)

            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(data),
                encoding="utf-8",
            )
            temporary.replace(cache_path)

            (self.cache_dir / "ATTRIBUTION.txt").write_text(
                ATTRIBUTION + "\n",
                encoding="utf-8",
            )

        return self._build_map_data(data, bounds)