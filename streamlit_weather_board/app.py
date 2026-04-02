"""Streamlit mini-dashboard: Open-Meteo current weather + 7-day high temps (stdlib HTTP)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd
import streamlit as st

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


@st.cache_data(ttl=300)
def fetch_forecast(lat: float, lon: float) -> dict:
    q = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
            "forecast_days": 7,
            "timezone": "auto",
        }
    )
    url = f"{OPEN_METEO}?{q}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        raise RuntimeError(f"Forecast request failed: {e}") from e


def main() -> None:
    st.set_page_config(
        page_title="Weather board",
        page_icon="🌤️",
        layout="centered",
    )
    st.title("Open-Meteo weather board")
    st.caption("Public work sample — browser UI + REST API, no API key.")

    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=52.52, format="%.4f", step=0.01)
    with col2:
        lon = st.number_input("Longitude", value=13.41, format="%.4f", step=0.01)

    if st.button("Load forecast", type="primary"):
        with st.spinner("Calling Open-Meteo…"):
            try:
                data = fetch_forecast(float(lat), float(lon))
            except RuntimeError as err:
                st.error(str(err))
                return

        cur = data.get("current") or {}
        temp = cur.get("temperature_2m")
        rh = cur.get("relative_humidity_2m")
        st.subheader("Now")
        m1, m2 = st.columns(2)
        with m1:
            if temp is not None:
                st.metric("Temperature", f"{temp} °C")
        with m2:
            if rh is not None:
                st.metric("Humidity", f"{rh} %")

        daily = data.get("daily") or {}
        times = daily.get("time") or []
        highs = daily.get("temperature_2m_max") or []
        lows = daily.get("temperature_2m_min") or []
        if times and highs:
            idx = pd.DatetimeIndex(pd.to_datetime(times))
            if lows and len(lows) == len(times) and all(
                x is not None for x in lows
            ):
                st.subheader("Next days (daily high and low)")
                chart_df = pd.DataFrame(
                    {"High °C": highs, "Low °C": lows},
                    index=idx,
                )
                chart_df.index.name = "Date"
                st.line_chart(chart_df)
            else:
                st.subheader("Next days (daily high)")
                chart_df = pd.DataFrame({"High °C": highs}, index=idx)
                chart_df.index.name = "Date"
                st.line_chart(chart_df)


if __name__ == "__main__":
    main()
