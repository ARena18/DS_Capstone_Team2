import plotly.express as px


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
    def generate(self, result: dict):
        df = result.get("data")
        if df is None or df.empty:
            return None

        chart_type = result.get("chart_type", "bar")
        x = result.get("x")
        y = result.get("y")
        color = result.get("color")

        if x not in df.columns or y not in df.columns:
            return None

        # Truncate long labels
        df = df.copy()
        if df[x].dtype == object:
            df[x] = df[x].astype(str).str[:30]

        template = "plotly_dark"

        if chart_type == "grouped_bar" and color and color in df.columns:
            fig = px.bar(
                df,
                x=x,
                y=y,
                color=color,
                barmode="group",
                template=template,
                color_discrete_sequence=COLORS,
            )
        elif chart_type == "line":
            fig = px.line(
                df,
                x=x,
                y=y,
                template=template,
                color_discrete_sequence=COLORS,
            )
        else:
            fig = px.bar(
                df,
                x=x,
                y=y,
                template=template,
                color_discrete_sequence=COLORS,
            )

        fig.update_layout(
            plot_bgcolor="#f5f5da",
            paper_bgcolor="#f5f5da",
            font_color="#1a1a1a",
            font=dict(size=30, color="#1a1a1a"),
            xaxis=dict(title_font=dict(size=17), tickfont=dict(size=17), tickangle=-45),
            yaxis=dict(title_font=dict(size=17), tickfont=dict(size=17)),
            margin=dict(l=40, r=20, t=50, b=120),
        )
        return fig
