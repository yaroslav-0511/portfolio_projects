# Open-Meteo CLI (stdlib only)

**Public sample** — fetches **current air temperature** from the free [Open-Meteo](https://open-meteo.com/en/docs) API (no API key).

**Use case:** illustrates a minimal “call REST API → parse JSON → CLI output” deliverable.

## Usage

```bash
python main.py --lat 52.52 --lon 13.41
python main.py --lat 40.71 --lon -74.01 --units fahrenheit
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--lat` | required | Latitude (decimal) |
| `--lon` | required | Longitude (decimal) |
| `--units` | `celsius` | `celsius` or `fahrenheit` |

## Requirements

Python 3.10+ (`urllib`, `json`, `argparse` only).

## Note

Open-Meteo has its own terms for high-volume or commercial use — check their docs if you ship something beyond a personal or small internal tool.
