"""Coordinate-system parsing and geodesic measurements (pyproj)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pyproj import Geod, CRS

_GEOD = Geod(ellps="WGS84")


def crs_name_from_wkt(wkt: str | None) -> str:
    """Best-effort human name for a WKT string (handles ESRI-flavoured WKT)."""
    if not wkt:
        return "unknown"
    try:
        return CRS.from_user_input(wkt).name
    except Exception:
        m = re.search(r'(?:PROJCS|GEOGCS)\["([^"]+)"', wkt)
        return m.group(1) if m else "unparseable"


@dataclass
class Bounds:
    """Geographic bounds derived from 4 GPTS corner pairs (lat, lon)."""
    lats: list[float]
    lons: list[float]

    @property
    def lat_min(self) -> float: return min(self.lats)

    @property
    def lat_max(self) -> float: return max(self.lats)

    @property
    def lon_min(self) -> float: return min(self.lons)

    @property
    def lon_max(self) -> float: return max(self.lons)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.lat_min + self.lat_max) / 2, (self.lon_min + self.lon_max) / 2)

    @property
    def area_km2(self) -> float:
        area, _ = _GEOD.polygon_area_perimeter(self.lons, self.lats)
        return abs(area) / 1e6

    @property
    def span_km(self) -> tuple[float, float]:
        """(width, height) in km across the bounding rectangle."""
        clat, _ = self.center
        _, _, w = _GEOD.inv(self.lon_min, clat, self.lon_max, clat)
        _, _, h = _GEOD.inv(self.lon_min, self.lat_min, self.lon_min, self.lat_max)
        return (w / 1000.0, h / 1000.0)


def bounds_from_gpts(gpts: list[float]) -> Bounds:
    """GPTS is a flat list of lat,lon pairs (ISO 32000: latitude first)."""
    lats = gpts[0::2]
    lons = gpts[1::2]
    return Bounds(lats=lats, lons=lons)
