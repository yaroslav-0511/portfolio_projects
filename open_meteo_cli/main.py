#!/usr/bin/env python3
"""Fetch current temperature from Open-Meteo (standard library only)."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Print current temperature from Open-Meteo for lat/lon.",
    )
    p.add_argument("--lat", type=float, required=True, help="Latitude")
    p.add_argument("--lon", type=float, required=True, help="Longitude")
    p.add_argument(
        "--units",
        choices=("celsius", "fahrenheit"),
        default="celsius",
        help="Temperature unit for display",
    )
    return p.parse_args()


def build_url(lat: float, lon: float, temp_unit: str) -> str:
    # Open-Meteo: current=temperature_2m; temperature_unit for celsius vs fahrenheit
    q = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m",
            "temperature_unit": temp_unit,
        }
    )
    return f"https://api.open-meteo.com/v1/forecast?{q}"


def main() -> int:
    args = parse_args()
    url = build_url(args.lat, args.lon, args.units)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        return 1

    current = payload.get("current") or {}
    temp = current.get("temperature_2m")
    if temp is None:
        print("No temperature_2m in response.", file=sys.stderr)
        return 1

    unit = "°C" if args.units == "celsius" else "°F"
    print(f"Current temperature: {temp}{unit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
