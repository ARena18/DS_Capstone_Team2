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

@tool
def get_overcrowded_routes(service_change_num: str, time_period: str = None, top_n: int = 10) -> str:
    """
    Identify overcrowded routes based on KCM definition
    
    Args:
        service_change_num: Service change period identifier
        time_period: Optional filter (e.g., 'AM Peak', 'PM Peak')
        top_n: Number of routes (default 10)
    """
    try:
        top_n = int(top_n)
    except Exception:
        top_n = 10

    if time_period is not None:
        time_period = str(time_period).strip()
        if time_period == "":
            time_period = None

    df = query_lib.get_overcrowded_routes(
        service_change_num=service_change_num,
        time_period=time_period,
        top_n=top_n
    )

    if df is None or df.empty:
        return f"No overcrowded routes found for service change {service_change_num}."

    time_filter = f"**Time Period:** {time_period}  \n" if time_period else "**Time Period:** All  \n"

    return (
        f"### 🚨 Overcrowded Routes\n"
        f"**Service Change:** {service_change_num}  \n\n"
        f"{time_filter}"
        f"{_df_to_str(df)}"
    )

@tool
def compare_routes(route_ids: str, start_date: str, end_date: str) -> str:
    """
    Compare multiple routes side-by-side.
    
    Args:
        route_ids: Comma-separated route IDs (e.g., "40,7,E Line")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    # Parse comma-separated route IDs
    if isinstance(route_ids, str):
        route_list = [r.strip() for r in route_ids.split(",")]
    else:
        route_list = [str(route_ids)]

    df = query_lib.compare_routes(
        route_ids=route_list,
        start_date=start_date,
        end_date=end_date
    )

    if df is None or df.empty:
        return f"No data found for routes {route_ids} from {start_date} to {end_date}."

    return (
        f"### 🔄 Route Comparison\n"
        f"**Routes:** {', '.join(route_list)}  \n"
        f"**Range:** {start_date} → {end_date}  \n\n"
        f"{_df_to_str(df)}"
    )

@tool
def declining_routes(comparison_months: int = 3, threshold_pct: float = -10.0, min_trips: int = 100) -> str:
    """
    Identify routes with significant ridership decline.
    
    Args:
        comparison_months: Months to compare (default 3)
        threshold_pct: Decline threshold as negative % (default -10)
        min_trips: Minimum trips to include (default 100)
    """
    try:
        comparison_months = int(comparison_months)
        threshold_pct = float(threshold_pct)
        min_trips = int(min_trips)
    except Exception:
        comparison_months = 3
        threshold_pct = -10.0
        min_trips = 100

    df = query_lib.identify_declining_routes(
        comparison_months=comparison_months,
        threshold_pct=threshold_pct,
        min_trips=min_trips
    )

    if df is None or df.empty:
        return f"No declining routes found (threshold: {threshold_pct}%, min trips: {min_trips})."

    return (
        f"### 📉 Declining Routes\n"
        f"**Comparison Period:** Last {comparison_months} months vs previous {comparison_months} months  \n"
        f"**Threshold:** {threshold_pct}%  \n"
        f"**Min Trips:** {min_trips}  \n\n"
        f"{_df_to_str(df)}"
    )

@tool
def crowding_by_time_period(route_id: str = None, start_date: str = None, end_date: str = None) -> str:
    """
    Analyze crowding patterns by time of day.
    
    Args:
        route_id: Optional route filter
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    if route_id is not None:
        route_id = str(route_id).strip()
        if route_id == "":
            route_id = None

    df = query_lib.get_crowding_by_time_period(
        route_id=route_id,
        start_date=start_date,
        end_date=end_date
    )

    if df is None or df.empty:
        route_note = f" for Route {route_id}" if route_id else ""
        return f"No crowding data found{route_note} from {start_date} to {end_date}."

    route_line = f"**Route:** {route_id}  \n" if route_id else "**Route:** All routes  \n"

    return (
        f"### 🕐 Crowding by Time Period\n"
        f"**Range:** {start_date} → {end_date}  \n"
        f"{route_line}\n"
        f"{_df_to_str(df)}"
    )

@tool
def route_by_direction(route_id: str, start_date: str, end_date: str) -> str:
    """
    Compare inbound vs outbound performance for a route.
    
    Args:
        route_id: Route identifier
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    route_id = str(route_id).strip()

    df = query_lib.get_route_by_direction(
        route_id=route_id,
        start_date=start_date,
        end_date=end_date
    )

    if df is None or df.empty:
        return f"No directional data found for Route {route_id} from {start_date} to {end_date}."

    return (
        f"### ↔️ Directional Analysis — Route {route_id}\n"
        f"**Range:** {start_date} → {end_date}  \n\n"
        f"{_df_to_str(df)}"
    )

@tool
def ridership_by_day_type(route_id: str = None, start_date: str = None, end_date: str = None) -> str:
    """
    Analyze ridership by day type (Weekday/Saturday/Sunday/Holiday).
    
    Args:
        route_id: Optional route filter
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    if route_id is not None:
        route_id = str(route_id).strip()
        if route_id == "":
            route_id = None

    df = query_lib.get_ridership_by_day_type(
        route_id=route_id,
        start_date=start_date,
        end_date=end_date
    )

    if df is None or df.empty:
        route_note = f" for Route {route_id}" if route_id else ""
        return f"No data found{route_note} from {start_date} to {end_date}."

    route_line = f"**Route:** {route_id}  \n" if route_id else "**Route:** All routes  \n"

    return (
        f"### 📆 Ridership by Day Type\n"
        f"**Range:** {start_date} → {end_date}  \n"
        f"{route_line}\n"
        f"{_df_to_str(df)}"
    )

# ================================================================
# TOOL REGISTRY
# ================================================================

# List of all available tools for easy import
ALL_TOOLS = [
    top_routes_by_ridership,
    route_ridership_trend,
    busiest_stops,
    service_change_impact,
    # New
    get_overcrowded_routes,
    compare_routes,
    declining_routes,
    crowding_by_time_period,
    route_by_direction,
    ridership_by_day_type,
]

def get_all_tools():
    """Return list of all available tools"""
    return ALL_TOOLS

def get_tool_names():
    """Return list of all tool names"""
    return [tool.name for tool in ALL_TOOLS]

