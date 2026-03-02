import plotly.express as px


COLORS = ["#4fc3f7", "#81c784", "#ffb74d", "#f06292", "#ce93d8"]


class VisualizationAgent:
    def generate(self, result: dict):
        df = result.get("data")
        if df is None or df.empty:
            return None

        chart_type = result.get("chart_type", "bar")
        x = result.get("x")
        y = result.get("y")
        color = result.get("color")
        title = result.get("title", "")

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
                title=title,
                template=template,
                color_discrete_sequence=COLORS,
            )
        elif chart_type == "line":
            fig = px.line(
                df,
                x=x,
                y=y,
                title=title,
                template=template,
                color_discrete_sequence=COLORS,
            )
        else:
            fig = px.bar(
                df,
                x=x,
                y=y,
                title=title,
                template=template,
                color_discrete_sequence=COLORS,
            )

        fig.update_layout(
            plot_bgcolor="#0f1117",
            paper_bgcolor="#0f1117",
            font=dict(color="#e8e8e8", family="IBM Plex Sans"),
            title_font=dict(size=14, color="#4fc3f7"),
            xaxis=dict(tickangle=-45),
            margin=dict(l=40, r=20, t=50, b=120),
        )
        return fig
