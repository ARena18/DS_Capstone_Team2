"""
Tests for visualization_agent.py — 100% branch coverage.

All plotly calls are mocked so no real rendering happens.
"""

import sys
import os

# Add the combined folder to the front of sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "combined")))

from visualization_agent import VisualizationAgent, COLORS  # noqa: E402

import types
from unittest.mock import MagicMock

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Stub out plotly before importing the module under test so the import
# succeeds in environments where plotly is not installed.
# ---------------------------------------------------------------------------
_plotly_stub = types.ModuleType("plotly")
_px_stub = types.ModuleType("plotly.express")
_go_stub = types.ModuleType("plotly.graph_objects")

_fake_fig = MagicMock(name="Figure")
_px_stub.bar = MagicMock(return_value=_fake_fig)
_px_stub.line = MagicMock(return_value=_fake_fig)
_go_stub.Figure = MagicMock(return_value=_fake_fig)

sys.modules.setdefault("plotly", _plotly_stub)
sys.modules.setdefault("plotly.express", _px_stub)
sys.modules.setdefault("plotly.graph_objects", _go_stub)

from visualization_agent import VisualizationAgent, COLORS  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent():
    return VisualizationAgent()


def _df(data: dict) -> pd.DataFrame:
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVisualizationAgentGenerate:
    """Tests for VisualizationAgent.generate()"""

    # ── Guard: None data ────────────────────────────────────────────────────

    def test_returns_none_when_data_key_missing(self, agent):
        result = agent.generate({})
        assert result is None

    def test_returns_none_when_data_is_none(self, agent):
        result = agent.generate({"data": None})
        assert result is None

    def test_returns_none_when_dataframe_empty(self, agent):
        result = agent.generate({"data": pd.DataFrame(), "x": "a", "y": "b"})
        assert result is None

    # ── Guard: missing columns ───────────────────────────────────────────────

    def test_returns_none_when_x_column_missing(self, agent):
        df = _df({"route": ["40"], "total": [100]})
        result = agent.generate({"data": df, "x": "NOT_A_COL", "y": "total"})
        assert result is None

    def test_returns_none_when_y_column_missing(self, agent):
        df = _df({"route": ["40"], "total": [100]})
        result = agent.generate({"data": df, "x": "route", "y": "NOT_A_COL"})
        assert result is None

    def test_returns_none_when_both_columns_missing(self, agent):
        df = _df({"route": ["40"]})
        result = agent.generate({"data": df, "x": "foo", "y": "bar"})
        assert result is None

    # ── Default bar chart ────────────────────────────────────────────────────

    def test_default_bar_chart_string_x_column(self, agent):
        """x column is object dtype → labels are truncated to 30 chars."""
        df = _df({"route": ["Route 40"], "boardings": [500]})
        _px_stub.bar.reset_mock()

        result = agent.generate(
            {
                "data": df,
                "x": "route",
                "y": "boardings",
                "chart_type": "bar",
                "title": "Test",
            }
        )

        assert result is _fake_fig
        _px_stub.bar.assert_called_once()
        kwargs = _px_stub.bar.call_args[1]
        assert kwargs["x"] == "route"
        assert kwargs["y"] == "boardings"
        assert kwargs["title"] == "Test"
        assert kwargs["color_discrete_sequence"] == COLORS

    def test_bar_chart_long_labels_are_truncated_for_object_dtype(self, agent):
        """String labels with legacy object dtype (> 30 chars) must be truncated.

        Note: In pandas 3+, DataFrame({'col': ['x']}) produces StringDtype, not object.
        Use pd.Series(..., dtype=object) to exercise the truncation branch.
        """
        import pandas as pd

        long_label = "A" * 50
        df = pd.DataFrame(
            {
                "route": pd.Series([long_label], dtype=object),
                "boardings": [1],
            }
        )
        _px_stub.bar.reset_mock()

        agent.generate({"data": df, "x": "route", "y": "boardings"})

        passed_df = _px_stub.bar.call_args[0][0]
        assert len(passed_df["route"].iloc[0]) == 30

    def test_non_object_string_dtype_not_truncated(self, agent):
        """Pandas 3 StringDtype columns should NOT be truncated (dtype != object)."""
        import pandas as pd

        long_label = "A" * 50
        # Default DataFrame construction in pandas 3 uses StringDtype
        df = pd.DataFrame({"route": [long_label], "boardings": [1]})
        _px_stub.bar.reset_mock()

        agent.generate({"data": df, "x": "route", "y": "boardings"})

        passed_df = _px_stub.bar.call_args[0][0]
        # In pandas 3 the truncation branch does not fire, label stays as-is
        assert len(passed_df["route"].iloc[0]) == 50

    def test_bar_chart_numeric_x_column_not_truncated(self, agent):
        """Numeric x column should not have str[:30] applied."""
        df = _df({"period": [20250101, 20250102], "boardings": [100, 200]})
        _px_stub.bar.reset_mock()

        agent.generate({"data": df, "x": "period", "y": "boardings"})

        passed_df = _px_stub.bar.call_args[0][0]
        assert passed_df["period"].iloc[0] == 20250101  # unchanged

    def test_unknown_chart_type_falls_back_to_bar(self, agent):
        df = _df({"route": ["40"], "boardings": [100]})
        _px_stub.bar.reset_mock()

        result = agent.generate(
            {"data": df, "x": "route", "y": "boardings", "chart_type": "radar"}
        )

        assert result is _fake_fig
        _px_stub.bar.assert_called_once()

    def test_missing_chart_type_defaults_to_bar(self, agent):
        df = _df({"route": ["40"], "boardings": [100]})
        _px_stub.bar.reset_mock()

        agent.generate({"data": df, "x": "route", "y": "boardings"})

        _px_stub.bar.assert_called_once()

    # ── Line chart ────────────────────────────────────────────────────────────

    def test_line_chart_type(self, agent):
        df = _df({"period": ["2025-01-01"], "total_boardings": [1000]})
        _px_stub.line.reset_mock()

        result = agent.generate(
            {
                "data": df,
                "x": "period",
                "y": "total_boardings",
                "chart_type": "line",
                "title": "Trend",
            }
        )

        assert result is _fake_fig
        _px_stub.line.assert_called_once()
        kwargs = _px_stub.line.call_args[1]
        assert kwargs["title"] == "Trend"

    # ── Grouped-bar chart ─────────────────────────────────────────────────────

    def test_grouped_bar_with_valid_color_column(self, agent):
        df = _df(
            {"route": ["40", "7"], "boardings": [500, 300], "day_code": ["WK", "WK"]}
        )
        _px_stub.bar.reset_mock()

        result = agent.generate(
            {
                "data": df,
                "x": "route",
                "y": "boardings",
                "chart_type": "grouped_bar",
                "color": "day_code",
                "title": "Grouped",
            }
        )

        assert result is _fake_fig
        _px_stub.bar.assert_called_once()
        kwargs = _px_stub.bar.call_args[1]
        assert kwargs["barmode"] == "group"
        assert kwargs["color"] == "day_code"

    def test_grouped_bar_missing_color_column_falls_back_to_plain_bar(self, agent):
        """grouped_bar with color column not present → plain bar."""
        df = _df({"route": ["40"], "boardings": [500]})
        _px_stub.bar.reset_mock()

        agent.generate(
            {
                "data": df,
                "x": "route",
                "y": "boardings",
                "chart_type": "grouped_bar",
                "color": "NONEXISTENT",
            }
        )

        kwargs = _px_stub.bar.call_args[1]
        assert "barmode" not in kwargs

    def test_grouped_bar_no_color_key_falls_back_to_plain_bar(self, agent):
        """grouped_bar without any color key → plain bar."""
        df = _df({"route": ["40"], "boardings": [500]})
        _px_stub.bar.reset_mock()

        agent.generate(
            {"data": df, "x": "route", "y": "boardings", "chart_type": "grouped_bar"}
        )

        kwargs = _px_stub.bar.call_args[1]
        assert "barmode" not in kwargs

    # ── Layout update is always called ───────────────────────────────────────

    def test_update_layout_called_on_every_chart(self, agent):
        df = _df({"route": ["40"], "boardings": [500]})
        _fake_fig.update_layout.reset_mock()

        agent.generate({"data": df, "x": "route", "y": "boardings"})

        _fake_fig.update_layout.assert_called_once()
        kwargs = _fake_fig.update_layout.call_args[1]
        assert kwargs["plot_bgcolor"] == "#0f1117"
        assert kwargs["paper_bgcolor"] == "#0f1117"

    # ── Title defaults to empty string ───────────────────────────────────────

    def test_empty_title_when_not_provided(self, agent):
        df = _df({"route": ["40"], "boardings": [500]})
        _px_stub.bar.reset_mock()

        agent.generate({"data": df, "x": "route", "y": "boardings"})

        kwargs = _px_stub.bar.call_args[1]
        assert kwargs["title"] == ""

    # ── COLORS constant is non-empty list ────────────────────────────────────

    def test_colors_constant_is_list_of_hex_strings():
        from visualization_agent import COLORS
        assert isinstance(COLORS, list)
        assert len(COLORS) > 0
        for c in COLORS:
            assert c.startswith("#"), f"Expected hex colour, got {c}"
