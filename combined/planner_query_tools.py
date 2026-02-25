import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sqlalchemy import create_engine
from langchain_core.tools import tool

from data_pipeline.query_library import TransitQueryLibrary

load_dotenv()

def _build_engine():
    host = os.getenv("SQL_HOST", "localhost").strip('"')
    port = os.getenv("SQL_PORT", "5432").strip('"')
    db   = os.getenv("SQL_DATABASE", "transit_db").strip('"')
    user = os.getenv("SQL_USERNAME", "").strip('"')
    pwd  = os.getenv("SQL_PASSWORD", "").strip('"')

    # password optional for local dev
    if pwd:
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    else:
        url = f"postgresql+psycopg2://{user}@{host}:{port}/{db}"

    return create_engine(url)

_engine = _build_engine()
query_lib = TransitQueryLibrary(_engine)  # expects db_engine in constructor:contentReference[oaicite:2]{index=2}

def _df_to_str(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df is None:
        return "No results."
    if len(df) > max_rows:
        df = df.head(max_rows)
    return df.to_markdown(index=False)

@tool
def top_routes_by_ridership(start_date: str, end_date: str, top_n: int = 10,
                            day_code: str = None, direction: str = None) -> str:
    """Top routes by boardings for a date range. day_code: WK/SA/SU/HOL. direction: I, O"""

    try:
        top_n = int(top_n)
    except Exception:
        top_n = 10

    user_prompt_lower = ""
    try:
        import streamlit as st
        user_prompt_lower = st.session_state.messages[-1]["content"].lower()
    except Exception:
        pass

    # Only apply day_code and direction filter if user mentioned it
    if day_code and not any(x in user_prompt_lower for x in ["wk", "weekday", "weekend", "sa", "su", "hol"]):
        day_code = None

    if direction and not any(x in user_prompt_lower for x in ["inbound", "outbound", "direction"]):
        direction = None

    df = query_lib.get_top_routes_by_ridership(
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
        day_code=day_code,
        direction=direction,
    )

    if df is None or df.empty:
        return f"No route activity found from {start_date} to {end_date}."

    # Build filter description
    filter_text = ""
    if day_code:
        filter_text += f"Day Type: {day_code}  \n"
    if direction:
        filter_text += f"Direction: {direction}  \n"
    if not filter_text:
        filter_text = "Filters: None  \n"

    return (
        f"### 🚌 Top {top_n} Routes by Ridership\n"
        f"**Date Range:** {start_date} → {end_date}  \n"
        f"{filter_text}\n"
        f"{_df_to_str(df)}"
    )

@tool
def route_ridership_trend(route_id: str, start_date: str, end_date: str, aggregation: str = "daily") -> str:
    """
    Ridership trend for a route over time.
    aggregation must be: daily, weekly, or monthly.
    """
    route_id = str(route_id).strip()

    agg = (aggregation or "daily").lower().strip()
    if agg not in {"daily", "weekly", "monthly"}:
        agg = "daily"

    df = query_lib.get_route_ridership_trend(
        route_id=route_id,
        start_date=start_date,
        end_date=end_date,
        aggregation=agg
    )

    if df is None or df.empty:
        return f"No results for Route {route_id} from {start_date} to {end_date} ({agg})."

    # Limit rows to avoid huge output
    max_rows = 20
    shown = df.head(max_rows)

    # Summary line
    total_boardings = float(df["total_boardings"].sum())
    total_trips = int(df["trip_count"].sum())
    avg_load = float(df["avg_max_psngr_load"].mean())

    return (
        f"### 📈 Ridership Trend — Route {route_id}\n"
        f"**Range:** {start_date} → {end_date}  \n"
        f"**Aggregation:** {agg}  \n"
        f"**Summary:** \n"
        f"- Total boardings = **{total_boardings:,.0f}**, \n"
        f"- Total trips = **{total_trips:,}**, \n"
        f"- Avg max load = **{avg_load:.2f}**  \n\n"
        f"**First {min(len(df), max_rows)} rows:**\n\n"
        f"{shown.to_markdown(index=False)}"
    )

@tool
def busiest_stops(start_date: str, end_date: str, route_id: str = None, top_n: int = 10, metric: str = "boardings") -> str:
    """
    Return busiest stops by total boardings or total alightings.
    metric must be 'boardings' or 'alightings'.
    """
    try:
        top_n = int(top_n)
    except Exception:
        top_n = 10

    m = (metric or "boardings").lower().strip()
    if m in {"boarding", "board"}:
        m = "boardings"
    elif m in {"alighting", "alight"}:
        m = "alightings"
    elif m not in {"boardings", "alightings"}:
        m = "boardings"

    if route_id is not None:
        route_id = str(route_id).strip()
        if route_id == "":
            route_id = None

    df = query_lib.get_busiest_stops(
        start_date=start_date,
        end_date=end_date,
        route_id=route_id,
        top_n=top_n,
        metric=m
    )

    if df is None or df.empty:
        route_note = f" for route {route_id}" if route_id else ""
        return f"No stop activity found{route_note} from {start_date} to {end_date}."

    shown = df.head(20)

    route_line = f"**Route filter:** {route_id}  \n" if route_id else "**Route filter:** None  \n"

    return (
        f"### 🛑 Busiest Stops ({m})\n"
        f"**Range:** {start_date} → {end_date}  \n"
        f"{route_line}"
        f"**Top N requested:** {top_n}  \n\n"
        f"{shown.to_markdown(index=False)}"
    )

@tool
def service_change_impact(route_id: str, change_date: str, window_days: int = 30) -> str:
    """
    Analyze ridership impact before/after a service change.
    change_date must be YYYY-MM-DD.
    window_days defaults to 30.
    """
    route_id = str(route_id)

    try:
        window_days = int(window_days)
    except Exception:
        window_days = 30

    result = query_lib.analyze_service_change_impact(
        route_id=route_id,
        change_date=change_date,
        window_days=window_days
    )
    before = result["before_period"]
    after = result["after_period"]
    impact = result["impact"]

    return f"""\
### 📊 Service Change Impact — Route {route_id}

**Change Date:** {change_date}  
**Window:** {window_days} days before/after  

#### BEFORE
- Trips: {before.get('trips', 0)}
- Avg Boardings per Trip: {before.get('avg_boardings_per_trip', 0)}
- Avg Max Passenger Load: {before.get('avg_max_psngr_load', 0)}
- Crowded Trips: {before.get('crowded_trips', 0)}

#### AFTER
- Trips: {after.get('trips', 0)}
- Avg Boardings per Trip: {after.get('avg_boardings_per_trip', 0)}
- Avg Max Passenger Load: {after.get('avg_max_psngr_load', 0)}
- Crowded Trips: {after.get('crowded_trips', 0)}

#### IMPACT
- Boardings Change: {impact.get('boardings_change', 0)}
- Percent Change: {impact.get('boardings_pct_change', 0)}%
- Direction: {impact.get('direction', 'n/a')}
- Significant (>5%): {impact.get('significant', False)}
"""
