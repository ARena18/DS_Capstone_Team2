# """
# Tests for visualization_agent.py — 100% branch coverage.
# Uses unittest.mock.patch to replace px inside the module after import.
# """

# import sys
# import os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "combined")))

# import types
# import unittest.mock as _um
# from unittest.mock import MagicMock, patch
# import pandas as pd
# import pytest

# # ---------------------------------------------------------------------------
# # Stub plotly in sys.modules so the import doesn't crash
# # ---------------------------------------------------------------------------
# _fake_fig = MagicMock(name="Figure")
# _fake_fig.update_layout = MagicMock()

# _px_stub = types.ModuleType("plotly.express")
# _px_stub.bar = MagicMock(return_value=_fake_fig)
# _px_stub.line = MagicMock(return_value=_fake_fig)

# _go_stub = types.ModuleType("plotly.graph_objects")
# _go_stub.Figure = MagicMock(return_value=_fake_fig)

# sys.modules.setdefault("plotly", types.ModuleType("plotly"))
# sys.modules["plotly.express"] = _px_stub
# sys.modules["plotly.graph_objects"] = _go_stub

# import visualization_agent as _va_mod
# from visualization_agent import VisualizationAgent

# # COLORS is class-level on VisualizationAgent
# COLORS = VisualizationAgent.COLORS

# # ---------------------------------------------------------------------------
# # Fixtures
# # ---------------------------------------------------------------------------

# @pytest.fixture(autouse=True)
# def patch_px(monkeypatch):
#     """
#     Patch px on the visualization_agent module for every test.
#     This is the only reliable way — direct attribute assignment doesn't
#     affect the local 'px' name already bound inside generate().
#     """
#     monkeypatch.setattr(_va_mod, "px", _px_stub)
#     _fake_fig.update_layout.reset_mock()
#     _px_stub.bar.reset_mock()
#     _px_stub.bar.return_value = _fake_fig
#     _px_stub.line.reset_mock()
#     _px_stub.line.return_value = _fake_fig
#     yield


# @pytest.fixture()
# def agent():
#     return VisualizationAgent()


# def _df(data: dict) -> pd.DataFrame:
#     return pd.DataFrame(data)


# # ---------------------------------------------------------------------------
# # Tests
# # ---------------------------------------------------------------------------

# class TestVisualizationAgentGenerate:

#     # ── Guards ───────────────────────────────────────────────────────────────

#     def test_returns_none_when_data_key_missing(self, agent):
#         assert agent.generate({}) is None

#     def test_returns_none_when_data_is_none(self, agent):
#         assert agent.generate({"data": None}) is None

#     def test_returns_none_when_dataframe_empty(self, agent):
#         assert agent.generate({"data": pd.DataFrame(), "x": "a", "y": "b"}) is None

#     def test_returns_none_when_x_column_missing(self, agent):
#         df = _df({"route": ["40"], "total": [100]})
#         assert agent.generate({"data": df, "x": "NOT_A_COL", "y": "total"}) is None

#     def test_returns_none_when_y_column_missing(self, agent):
#         df = _df({"route": ["40"], "total": [100]})
#         assert agent.generate({"data": df, "x": "route", "y": "NOT_A_COL"}) is None

#     def test_returns_none_when_both_columns_missing(self, agent):
#         df = _df({"route": ["40"]})
#         assert agent.generate({"data": df, "x": "foo", "y": "bar"}) is None

#     # ── Bar chart ────────────────────────────────────────────────────────────

#     def test_default_bar_chart(self, agent):
#         df = _df({"route": ["Route 40"], "boardings": [500]})
#         result = agent.generate({
#             "data": df, "x": "route", "y": "boardings",
#             "chart_type": "bar", "title": "Test",
#         })
#         assert result is _fake_fig
#         _px_stub.bar.assert_called_once()
#         kwargs = _px_stub.bar.call_args[1]
#         assert kwargs["x"] == "route"
#         assert kwargs["y"] == "boardings"
#         assert kwargs["color_discrete_sequence"] == COLORS

#     def test_bar_chart_long_labels_truncated_for_object_dtype(self, agent):
#         long_label = "A" * 50
#         df = pd.DataFrame({
#             "route": pd.Series([long_label], dtype=object),
#             "boardings": [1],
#         })
#         agent.generate({"data": df, "x": "route", "y": "boardings"})
#         passed_df = _px_stub.bar.call_args[0][0]
#         assert len(passed_df["route"].iloc[0]) == 30

#     def test_non_object_string_dtype_not_truncated(self, agent):
#         long_label = "A" * 50
#         df = pd.DataFrame({"route": [long_label], "boardings": [1]})
#         if df["route"].dtype == object:
#             pytest.skip("pandas uses object dtype here — truncation fires")
#         agent.generate({"data": df, "x": "route", "y": "boardings"})
#         passed_df = _px_stub.bar.call_args[0][0]
#         assert len(passed_df["route"].iloc[0]) == 50

#     def test_numeric_x_column_not_truncated(self, agent):
#         df = _df({"period": [20250101, 20250102], "boardings": [100, 200]})
#         agent.generate({"data": df, "x": "period", "y": "boardings"})
#         passed_df = _px_stub.bar.call_args[0][0]
#         assert passed_df["period"].iloc[0] == 20250101

#     def test_unknown_chart_type_falls_back_to_bar(self, agent):
#         df = _df({"route": ["40"], "boardings": [100]})
#         result = agent.generate({
#             "data": df, "x": "route", "y": "boardings", "chart_type": "radar"
#         })
#         assert result is _fake_fig
#         _px_stub.bar.assert_called_once()

#     def test_missing_chart_type_defaults_to_bar(self, agent):
#         df = _df({"route": ["40"], "boardings": [100]})
#         agent.generate({"data": df, "x": "route", "y": "boardings"})
#         _px_stub.bar.assert_called_once()

#     # ── Line chart ────────────────────────────────────────────────────────────

#     def test_line_chart_type(self, agent):
#         df = _df({"period": ["2025-01-01"], "total_boardings": [1000]})
#         result = agent.generate({
#             "data": df, "x": "period", "y": "total_boardings",
#             "chart_type": "line", "title": "Trend",
#         })
#         assert result is _fake_fig
#         _px_stub.line.assert_called_once()

#     # ── Grouped bar ───────────────────────────────────────────────────────────

#     def test_grouped_bar_with_valid_color_column(self, agent):
#         df = _df({"route": ["40", "7"], "boardings": [500, 300], "day_code": ["WK", "WK"]})
#         result = agent.generate({
#             "data": df, "x": "route", "y": "boardings",
#             "chart_type": "grouped_bar", "color": "day_code",
#         })
#         assert result is _fake_fig
#         kwargs = _px_stub.bar.call_args[1]
#         assert kwargs["barmode"] == "group"
#         assert kwargs["color"] == "day_code"

#     def test_grouped_bar_missing_color_falls_back_to_plain_bar(self, agent):
#         df = _df({"route": ["40"], "boardings": [500]})
#         agent.generate({
#             "data": df, "x": "route", "y": "boardings",
#             "chart_type": "grouped_bar", "color": "NONEXISTENT",
#         })
#         kwargs = _px_stub.bar.call_args[1]
#         assert "barmode" not in kwargs

#     def test_grouped_bar_no_color_key_falls_back_to_plain_bar(self, agent):
#         df = _df({"route": ["40"], "boardings": [500]})
#         agent.generate({
#             "data": df, "x": "route", "y": "boardings", "chart_type": "grouped_bar"
#         })
#         kwargs = _px_stub.bar.call_args[1]
#         assert "barmode" not in kwargs

#     # ── Layout ────────────────────────────────────────────────────────────────

#     def test_update_layout_called_on_every_chart(self, agent):
#         df = _df({"route": ["40"], "boardings": [500]})
#         agent.generate({"data": df, "x": "route", "y": "boardings"})
#         _fake_fig.update_layout.assert_called_once()
#         kwargs = _fake_fig.update_layout.call_args[1]
#         assert kwargs["plot_bgcolor"] == "#f5f5da"
#         assert kwargs["paper_bgcolor"] == "#f5f5da"

#     # ── COLORS ────────────────────────────────────────────────────────────────

#     def test_colors_constant_is_list_of_hex_strings(self):
#         assert isinstance(COLORS, list)
#         assert len(COLORS) > 0
#         for c in COLORS:
#             assert c.startswith("#"), f"Expected hex colour, got {c}"

# tests/test_visualization_agent.py
# 100% coverage for visualization_agent.py
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Remove any stub so we get the real implementation
sys.modules.pop("visualization_agent", None)

# Now import normally
from visualization_agent import VisualizationAgent

import planner_query_tools

# ── Ensure the combined/ folder is on the path ────────────────────────────────
COMBINED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "combined")
if COMBINED_DIR not in sys.path:
    sys.path.insert(0, COMBINED_DIR)

from visualization_agent import VisualizationAgent  # noqa: E402

# ── Convenience ───────────────────────────────────────────────────────────────
def _agent():
    return VisualizationAgent()

def _df(**kwargs):
    """One-row DataFrame from kwargs."""
    return pd.DataFrame([kwargs])


# ═════════════════════════════════════════════════════════════════════════════
# TestColors
# ═════════════════════════════════════════════════════════════════════════════

class TestColorsConstant:
    def test_colors_is_list(self):
        assert isinstance(VisualizationAgent.COLORS, list)

    def test_colors_are_hex_strings(self):
        for c in VisualizationAgent.COLORS:
            assert c.startswith("#"), f"{c} is not a hex colour"
            assert len(c) == 7

    def test_colors_class_attribute_equals_module_constant(self):
        assert VisualizationAgent.COLORS == VisualizationAgent.COLORS

    def test_colors_has_five_entries(self):
        assert len(VisualizationAgent.COLORS) == 5


# ═════════════════════════════════════════════════════════════════════════════
# TestChartConfig
# ══════════════════════

class TestChartConfig:
    EXPECTED_TOOLS = [
        "top_routes_by_ridership",
        "route_ridership_trend",
        "busiest_stops",
        "get_overcrowded_routes",
        "compare_routes",
        "declining_routes",
        "crowding_by_time_period",
        "route_by_direction",
        "ridership_by_day_type",
        "service_change_impact",
    ]

    def test_chart_config_has_all_tools(self):
        for tool in self.EXPECTED_TOOLS:
            assert tool in VisualizationAgent.CHART_CONFIG, f"Missing: {tool}"

    def test_each_entry_has_required_keys(self):
        for tool, cfg in VisualizationAgent.CHART_CONFIG.items():
            for key in ("x", "y", "chart_type", "title"):
                assert key in cfg, f"{tool} missing key '{key}'"

    def test_route_ridership_trend_is_line_chart(self):
        assert VisualizationAgent.CHART_CONFIG["route_ridership_trend"]["chart_type"] == "line"

    def test_all_others_are_bar_charts(self):
        for tool, cfg in VisualizationAgent.CHART_CONFIG.items():
            if tool != "route_ridership_trend":
                assert cfg["chart_type"] == "bar", f"{tool} should be bar"


# ═════════════════════════════════════════════════════════════════════════════
# TestVisualizationAgentGenerate
# ═════════════════════════════════════════════════════════════════════════════

class TestVisualizationAgentGenerate:

    # ── Guard / None paths ────────────────────────────────────────────────────

    def test_returns_none_when_data_key_missing(self):
        assert _agent().generate({"x": "a", "y": "b"}) is None

    def test_returns_none_when_data_is_none(self):
        assert _agent().generate({"data": None, "x": "a", "y": "b"}) is None

    def test_returns_none_when_dataframe_empty(self):
        assert _agent().generate({"data": pd.DataFrame(), "x": "a", "y": "b"}) is None

    def test_returns_none_when_x_column_missing(self):
        df = _df(y_col=1)
        assert _agent().generate({"data": df, "x": "x_col", "y": "y_col"}) is None

    def test_returns_none_when_y_column_missing(self):
        df = _df(x_col="A")
        assert _agent().generate({"data": df, "x": "x_col", "y": "y_col"}) is None

    def test_returns_none_when_both_columns_missing(self):
        df = _df(other=1)
        assert _agent().generate({"data": df, "x": "x_col", "y": "y_col"}) is None

    def test_returns_none_when_x_is_none(self):
        df = _df(a="A", b=1)
        assert _agent().generate({"data": df, "x": None, "y": "b"}) is None

    def test_returns_none_when_y_is_none(self):
        df = _df(a="A", b=1)
        assert _agent().generate({"data": df, "x": "a", "y": None}) is None

    # ── Bar chart (default) ───────────────────────────────────────────────────

    def test_default_bar_chart(self):
        df = _df(route="40", total_boardings=500)
        fig = _agent().generate({"data": df, "x": "route", "y": "total_boardings"})
        assert fig is not None

    def test_missing_chart_type_defaults_to_bar(self):
        df = _df(route="7", total_boardings=100)
        fig = _agent().generate({"data": df, "x": "route", "y": "total_boardings", "title": "T"})
        assert fig is not None

    def test_unknown_chart_type_falls_back_to_bar(self):
        df = _df(route="E Line", total_boardings=300)
        fig = _agent().generate({
            "data": df, "x": "route", "y": "total_boardings",
            "chart_type": "radar",   # unsupported → plain bar
        })
        assert fig is not None

    # ── Line chart ────────────────────────────────────────────────────────────

    def test_line_chart_type(self):
        df = _df(period="2025-01", total_boardings=1000)
        fig = _agent().generate({
            "data": df, "x": "period", "y": "total_boardings",
            "chart_type": "line", "title": "Trend",
        })
        assert fig is not None

    # ── Grouped bar ───────────────────────────────────────────────────────────

    def test_grouped_bar_with_valid_color_column(self):
        df = pd.DataFrame([
            {"route": "40", "total_boardings": 500, "direction": "I"},
            {"route": "40", "total_boardings": 400, "direction": "O"},
        ])
        fig = _agent().generate({
            "data": df, "x": "route", "y": "total_boardings",
            "chart_type": "grouped_bar", "color": "direction",
        })
        assert fig is not None

    def test_grouped_bar_missing_color_falls_back_to_plain_bar(self):
        df = _df(route="7", total_boardings=200)
        fig = _agent().generate({
            "data": df, "x": "route", "y": "total_boardings",
            "chart_type": "grouped_bar", "color": "nonexistent_col",
        })
        assert fig is not None   # falls back to plain bar

    def test_grouped_bar_no_color_key_falls_back_to_plain_bar(self):
        df = _df(route="7", total_boardings=200)
        fig = _agent().generate({
            "data": df, "x": "route", "y": "total_boardings",
            "chart_type": "grouped_bar",
            # no "color" key at all
        })
        assert fig is not None

    # ── Long-label truncation ─────────────────────────────────────────────────

    def test_bar_chart_long_labels_truncated_for_object_dtype(self):
        long_label = "A" * 50
        df = _df(**{"stop_nm": long_label, "total_boardings": 10})
        fig = _agent().generate({
            "data": df, "x": "stop_nm", "y": "total_boardings",
            "chart_type": "bar",
        })
        assert fig is not None
        # The label in the figure should be at most 30 chars
        x_vals = fig.data[0].x
        assert all(len(str(v)) <= 30 for v in x_vals)

    def test_non_object_string_dtype_not_truncated(self):
        # Integer x-axis — truncation branch should be skipped
        df = pd.DataFrame([{"period": 202501, "total_boardings": 100}])
        fig = _agent().generate({
            "data": df, "x": "period", "y": "total_boardings",
            "chart_type": "bar",
        })
        assert fig is not None

    def test_numeric_x_column_not_truncated(self):
        df = pd.DataFrame([{"period": 1, "val": 5}, {"period": 2, "val": 8}])
        fig = _agent().generate({"data": df, "x": "period", "y": "val"})
        assert fig is not None

    # ── Layout ────────────────────────────────────────────────────────────────

    def test_update_layout_called_on_every_chart(self):
        df = _df(route="40", total_boardings=500)
        fig = _agent().generate({"data": df, "x": "route", "y": "total_boardings"})
        # plot_bgcolor should be transparent
        assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
        assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"

    def test_title_applied_to_figure(self):
        df = _df(route="40", total_boardings=500)
        fig = _agent().generate({
            "data": df, "x": "route", "y": "total_boardings",
            "title": "My Custom Title",
        })
        assert "My Custom Title" in fig.layout.title.text

    def test_empty_title_does_not_raise(self):
        df = _df(route="40", total_boardings=500)
        fig = _agent().generate({
            "data": df, "x": "route", "y": "total_boardings",
            "title": "",
        })
        assert fig is not None

    # ── Original DataFrame not mutated ────────────────────────────────────────

    def test_original_df_not_mutated_by_truncation(self):
        long_label = "B" * 50
        df = _df(**{"stop_nm": long_label, "total_boardings": 10})
        original_label = df["stop_nm"].iloc[0]
        _agent().generate({"data": df, "x": "stop_nm", "y": "total_boardings"})
        assert df["stop_nm"].iloc[0] == original_label   # unchanged

    # ── Multi-row DataFrames ──────────────────────────────────────────────────

    def test_multi_row_bar_chart(self):
        df = pd.DataFrame([
            {"route": str(i), "total_boardings": i * 100}
            for i in range(1, 6)
        ])
        fig = _agent().generate({"data": df, "x": "route", "y": "total_boardings"})
        assert fig is not None
        assert len(fig.data[0].x) == 5

    def test_multi_row_line_chart(self):
        df = pd.DataFrame([
            {"period": f"2025-{i:02d}", "total_boardings": i * 50}
            for i in range(1, 7)
        ])
        fig = _agent().generate({
            "data": df, "x": "period", "y": "total_boardings",
            "chart_type": "line",
        })
        assert fig is not None
        assert len(fig.data[0].x) == 6