import plotly.express as px
import pandas as pd


COLORS = ["#81c784", "#4fc3f7", "#ffb74d", "#f06292", "#ce93d8"]

CHART_CONFIG = {
        "top_routes_by_ridership": {
            "x": "route",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Top Routes by Ridership",
        },
        "route_ridership_trend": {
            "x": "period",
            "y": "total_boardings",
            "chart_type": "line",
            "title": "Ridership Trend Over Time",
        },
        "busiest_stops": {
            "x": "stop_nm",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Busiest Stops",
        },
        "get_overcrowded_routes": {
            "x": "route",
            "y": "overcrowded_trips",
            "chart_type": "bar",
            "title": "Overcrowded Routes",
        },
        "compare_routes": {
            "x": "route",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Route Comparison",
        },
        "declining_routes": {
            "x": "route",
            "y": "boardings_pct_change",
            "chart_type": "bar",
            "title": "Declining Routes (% Change)",
        },
        "crowding_by_time_period": {
            "x": "time_period",
            "y": "pct_crowded",
            "chart_type": "bar",
            "title": "Crowding by Time Period",
        },
        "route_by_direction": {
            "x": "direction_label",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Ridership by Direction",
        },
        "ridership_by_day_type": {
            "x": "day_type",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Ridership by Day Type",
        },
        "service_change_impact": {
            "x": "period",
            "y": "avg_boardings_per_trip",
            "chart_type": "bar",
            "title": "Service Change Impact",
        },
    }

class VisualizationAgent:

    COLORS = COLORS

    CHART_CONFIG = {
        "top_routes_by_ridership": {
            "x": "route",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Top Routes by Ridership",
        },
        "route_ridership_trend": {
            "x": "period",
            "y": "total_boardings",
            "chart_type": "line",
            "title": "Ridership Trend Over Time",
        },
        "busiest_stops": {
            "x": "stop_nm",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Busiest Stops",
        },
        "get_overcrowded_routes": {
            "x": "route",
            "y": "overcrowded_trips",
            "chart_type": "bar",
            "title": "Overcrowded Routes",
        },
        "compare_routes": {
            "x": "route",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Route Comparison",
        },
        "declining_routes": {
            "x": "route",
            "y": "boardings_pct_change",
            "chart_type": "bar",
            "title": "Declining Routes (% Change)",
        },
        "crowding_by_time_period": {
            "x": "time_period",
            "y": "pct_crowded",
            "chart_type": "bar",
            "title": "Crowding by Time Period",
        },
        "route_by_direction": {
            "x": "direction_label",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Ridership by Direction",
        },
        "ridership_by_day_type": {
            "x": "day_type",
            "y": "total_boardings",
            "chart_type": "bar",
            "title": "Ridership by Day Type",
        },
        "service_change_impact": {
            "x": "period",
            "y": "avg_boardings_per_trip",
            "chart_type": "bar",
            "title": "Service Change Impact",
        },
    }

    def generate(self, cfg: dict):
        """
        Generate a Plotly figure from a config dict.

        Required keys: data (DataFrame), x (str), y (str)
        Optional keys: chart_type (str), title (str), color (str)

        Returns None if data is missing, None, empty, or required columns absent.
        """
        df = cfg.get("data")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return None

        x = cfg.get("x")
        y = cfg.get("y")

        if x is None or y is None:
            return None
        if x not in df.columns or y not in df.columns:
            return None

        # Truncate long string labels on the x-axis for readability
        if df[x].dtype == object:
            df = df.copy()
            df[x] = df[x].str[:30]

        chart_type = cfg.get("chart_type", "bar")
        title      = cfg.get("title", "")
        color_col  = cfg.get("color")

        # Validate color column exists
        if color_col and color_col not in df.columns:
            color_col = None

        if chart_type == "line":
            fig = px.line(
                df, x=x, y=y,
                title=title,
                color_discrete_sequence=COLORS,
            )
        elif chart_type == "grouped_bar" and color_col:
            fig = px.bar(
                df, x=x, y=y,
                color=color_col,
                barmode="group",
                title=title,
                color_discrete_sequence=COLORS,
            )
        else:
            # default: plain bar
            fig = px.bar(
                df, x=x, y=y,
                title=title,
                color_discrete_sequence=COLORS,
            )

        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#1a1a1a",
        )
        return fig

CHART_CONFIG = VisualizationAgent.CHART_CONFIG