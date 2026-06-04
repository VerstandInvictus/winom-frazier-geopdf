"""Verify every asset listed in app/sw.js exists on disk (prevents offline cache misses)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sw = (ROOT / "app" / "sw.js").read_text()
listed = re.findall(r'"\./([^"]+)"', sw)
missing = [a for a in listed if a and not (ROOT / "app" / a).exists()]
if missing:
    print("MISSING assets referenced by sw.js:", missing)
    sys.exit(1)
print(f"OK: all {len(listed)} sw.js assets present")
