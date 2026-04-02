# Streamlit weather board (Open-Meteo)

**Public work sample** — single-page **Streamlit** app: user picks latitude/longitude, loads [Open-Meteo](https://open-meteo.com/) forecast (no API key), shows **current metrics** and **7-day temperature charts**. Good for **portfolio screenshots** (browser UI).

**Stack:** Python 3.10+, Streamlit, **pandas** (for correct time-series charts), `urllib` + `json` for HTTP.

## What this sample shows

- Small data product in the browser
- Public REST API integration and basic error handling in UI
- `st.cache_data` to avoid hammering the API while tuning the UI

## Setup

```bash
cd portfolio_projects/streamlit_weather_board
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
streamlit run app.py
```

Opens a local URL in the browser (Streamlit prints the link).

### Ubuntu / Debian / WSL: `ensurepip is not available`

Install the matching venv package once (version must match `python3 --version`), then recreate `.venv`:

```bash
sudo apt update
sudo apt install python3.12-venv
# if your Python is 3.11, use: sudo apt install python3.11-venv
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## Notes

- Respect [Open-Meteo terms](https://open-meteo.com/) for non-demo traffic.
- For Fiverr/Upwork: capture 1–2 screenshots of the running app after loading a forecast.

## License

Public code sample — use and adapt freely; no warranty.
