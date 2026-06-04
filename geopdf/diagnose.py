"""Identify the main-map viewport, validate it, and recommend the fix."""
from __future__ import annotations
import json
from pathlib import Path
from geopdf.pdfgeo import decode_pdf


def point_in_bounds(lat: float, lon: float, b) -> bool:
    return b.lat_min <= lat <= b.lat_max and b.lon_min <= lon <= b.lon_max


def classify_viewport(b, known_points) -> str:
    lat_span = b.lat_max - b.lat_min
    lon_span = b.lon_max - b.lon_min
    if lat_span > 20 or lon_span > 20:
        return "continental"
    if b.area_km2 > 50_000:
        return "locator"
    if b.area_km2 < 2:
        return "inset"
    if known_points and not any(point_in_bounds(p["lat"], p["lon"], b) for p in known_points):
        return "off_region"
    return "main_map"


def load_known_points(path) -> list[dict]:
    if not Path(path).exists():
        return []
    return json.loads(Path(path).read_text()).get("points", [])


def diagnose(paths, known_points) -> dict:
    files = []
    for path in paths:
        path = Path(path)
        decoded = decode_pdf(path)
        classified = []
        main = None
        for vp in decoded.viewports:
            cls = classify_viewport(vp.bounds, known_points)
            classified.append({
                "name": vp.name, "class": cls,
                "area_km2": round(vp.bounds.area_km2, 3),
                "center": [round(vp.bounds.center[0], 5), round(vp.bounds.center[1], 5)],
                "gpts": vp.gpts,
            })
            if cls == "main_map" and main is None:
                main = vp
        validation = None
        if main is not None and known_points:
            inside = [p["name"] for p in known_points if point_in_bounds(p["lat"], p["lon"], main.bounds)]
            validation = {"inside_main": inside, "total": len(known_points),
                          "all_inside": len(inside) == len(known_points)}
        files.append({
            "filename": path.name,
            "georeferenced": len(decoded.viewports) > 0,
            "viewport_count": len(decoded.viewports),
            "main_map_name": main.name if main else None,
            "main_map_gpts": main.gpts if main else None,
            "classified": classified,
            "validation": validation,
        })
    needs_collapse = any(f["main_map_name"] and f["viewport_count"] > 1 for f in files)
    decision = "COLLAPSE_TO_SINGLE_VIEWPORT" if needs_collapse else "NO_ACTION"
    return {"files": files, "decision": decision, "known_point_count": len(known_points)}


def write_findings(result: dict, out_path) -> None:
    lines = ["# Winom-Frazier GeoPDF — Findings\n",
             f"**Recommended fix:** `{result['decision']}`  ",
             f"**Known points used for validation:** {result['known_point_count']}\n"]
    for f in result["files"]:
        lines.append(f"## {f['filename']}")
        lines.append(f"- Georeferenced: **{f['georeferenced']}**  |  viewports: {f['viewport_count']}")
        if f["main_map_name"]:
            lines.append(f"- Main-map viewport: **{f['main_map_name']}**  (keep this one when collapsing)")
        if f["validation"]:
            v = f["validation"]
            names = ", ".join(v["inside_main"]) or "none"
            lines.append(f"- Validation: {len(v['inside_main'])}/{v['total']} known points inside the main map "
                         f"(all inside: {v['all_inside']}) — {names}")
        if f["classified"]:
            lines.append("- Viewports:")
            for c in f["classified"]:
                lines.append(f"  - `{c['name']}` — {c['class']} ({c['area_km2']} km²)")
        lines.append("")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
