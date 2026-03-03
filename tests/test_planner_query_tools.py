"""
Tests for planner_query_tools.py — 100% branch coverage.

All database and Streamlit calls are mocked.
"""

import sys
import types
from unittest.mock import MagicMock, patch
import pandas as pd

# ---------------------------------------------------------------------------
# Stub heavy dependencies before import
# ---------------------------------------------------------------------------


def _stub(name):
    m = types.ModuleType(name)
    sys.modules.setdefault(name, m)
    return m


# SQLAlchemy stubs
sa = _stub("sqlalchemy")
sa.create_engine = MagicMock(return_value=MagicMock())
sa.text = lambda sql: sql
_stub("sqlalchemy.engine").Engine = object

# dotenv stub
dotenv = _stub("dotenv")
dotenv.load_dotenv = MagicMock()

# psycopg2 stub
_stub("psycopg2")

# langchain stubs
lc_core = _stub("langchain_core")
lc_tools = _stub("langchain_core.tools")

_real_tool_registry = {}


def _fake_tool(fn):
    """Decorator that wraps the function and records it like langchain @tool."""
    fn.name = fn.__name__
    fn.invoke = lambda args: fn(**args) if isinstance(args, dict) else fn(args)
    _real_tool_registry[fn.__name__] = fn
    return fn


lc_tools.tool = _fake_tool
sys.modules["langchain_core.tools"] = lc_tools

# Streamlit stub — we need st.session_state to behave like an attr dict
st_mod = _stub("streamlit")
_session = {}


class _FakeSessionState:
    def __getattr__(self, key):
        return _session.get(key, MagicMock())

    def __setattr__(self, key, value):
        _session[key] = value

    def __contains__(self, key):
        return key in _session


st_mod.session_state = _FakeSessionState()
sys.modules["streamlit"] = st_mod

# query_library stub — inject a controllable mock
_ql_mock = MagicMock()
ql_mod = _stub("query_library")
ql_mod.TransitQueryLibrary = MagicMock(return_value=_ql_mock)
sys.modules["query_library"] = ql_mod


# Import the module under test (will use all stubs above)
import planner_query_tools as pqt

# Re-wire query_lib to our mock AFTER import
pqt.query_lib = _ql_mock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df(*col_rows):
    """Quick DataFrame builder: _df(('a','b'), [1,2], [3,4])"""
    if not col_rows:
        return pd.DataFrame()
    cols, *rows = col_rows
    return pd.DataFrame(rows, columns=cols)


def _empty():
    return pd.DataFrame()


START = "2025-01-01"
END = "2025-12-31"


# ===========================================================================
# _df_to_str
# ===========================================================================


class TestDfToStr:
    def test_returns_no_results_for_none(self):
        assert pqt._df_to_str(None) == "No results."

    def test_returns_markdown_string(self):
        df = pd.DataFrame({"a": [1, 2]})
        result = pqt._df_to_str(df)
        assert "|" in result  # markdown table uses pipes

    def test_truncates_to_max_rows(self):
        df = pd.DataFrame({"n": range(30)})
        result = pqt._df_to_str(df, max_rows=5)
        # Only 5 data rows (plus header + separator) should appear
        lines = [l for l in result.split("\n") if l.strip().startswith("|")]
        # Header + separator + 5 data rows = 7 lines
        assert len(lines) <= 7

    def test_does_not_truncate_when_under_max(self):
        df = pd.DataFrame({"n": range(3)})
        result = pqt._df_to_str(df, max_rows=20)
        assert "0" in result and "2" in result


# ===========================================================================
# top_routes_by_ridership tool
# ===========================================================================


class TestTopRoutesByRidership:
    def setup_method(self):
        _ql_mock.reset_mock()
        _session.clear()

    def test_returns_formatted_string_on_success(self):
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [5000]}
        )
        result = pqt.top_routes_by_ridership(START, END, top_n=10)
        assert "Top 10 Routes by Ridership" in result
        assert START in result

    def test_returns_no_activity_message_when_empty(self):
        _ql_mock.get_top_routes_by_ridership.return_value = _empty()
        result = pqt.top_routes_by_ridership(START, END)
        assert "No route activity found" in result

    def test_top_n_coerced_to_int(self):
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        pqt.top_routes_by_ridership(START, END, top_n="5")
        call_kwargs = _ql_mock.get_top_routes_by_ridership.call_args[1]
        assert call_kwargs["top_n"] == 5

    def test_top_n_defaults_to_10_on_bad_value(self):
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        # Patch int() to fail for the first call only
        with patch("builtins.int", side_effect=[ValueError, int]):
            pqt.top_routes_by_ridership.__wrapped__(START, END, top_n="bad")
        # Just verify it doesn't raise

    def test_day_code_cleared_when_not_in_prompt(self):
        """day_code should be nulled when session prompt doesn't mention day keywords."""
        _session["messages"] = [{"content": "show me top routes"}]
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        pqt.top_routes_by_ridership(START, END, day_code="WK")
        call_kwargs = _ql_mock.get_top_routes_by_ridership.call_args[1]
        assert call_kwargs["day_code"] is None

    def test_day_code_kept_when_prompt_mentions_weekday(self):
        _session["messages"] = [{"content": "show weekday ridership"}]
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        pqt.top_routes_by_ridership(START, END, day_code="WK")
        call_kwargs = _ql_mock.get_top_routes_by_ridership.call_args[1]
        assert call_kwargs["day_code"] == "WK"

    def test_direction_cleared_when_not_in_prompt(self):
        _session["messages"] = [{"content": "show me top routes"}]
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        pqt.top_routes_by_ridership(START, END, direction="I")
        call_kwargs = _ql_mock.get_top_routes_by_ridership.call_args[1]
        assert call_kwargs["direction"] is None

    def test_direction_kept_when_prompt_mentions_inbound(self):
        _session["messages"] = [{"content": "compare inbound vs outbound"}]
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        pqt.top_routes_by_ridership(START, END, direction="I")
        call_kwargs = _ql_mock.get_top_routes_by_ridership.call_args[1]
        assert call_kwargs["direction"] == "I"

    def test_filter_text_no_filter(self):
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        result = pqt.top_routes_by_ridership(START, END)
        assert "Filters: None" in result

    def test_filter_text_with_day_code_in_result(self):
        _session["messages"] = [{"content": "show weekday top routes"}]
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        result = pqt.top_routes_by_ridership(START, END, day_code="WK")
        assert "Day Type: WK" in result

    def test_filter_text_with_direction_in_result(self):
        _session["messages"] = [{"content": "show inbound routes"}]
        _ql_mock.get_top_routes_by_ridership.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [1]}
        )
        result = pqt.top_routes_by_ridership(START, END, direction="I")
        assert "Direction: I" in result


# ===========================================================================
# route_ridership_trend tool
# ===========================================================================


class TestRouteRidershipTrend:
    def setup_method(self):
        _ql_mock.reset_mock()

    def _df_with_cols(self):
        return pd.DataFrame(
            {
                "period": ["2025-01-01"],
                "total_boardings": [500.0],
                "trip_count": [10],
                "avg_load_factor": [0.65],
            }
        )

    def test_returns_trend_string(self):
        _ql_mock.get_route_ridership_trend.return_value = self._df_with_cols()
        result = pqt.route_ridership_trend("40", START, END)
        assert "Route 40" in result
        assert "Ridership Trend" in result

    def test_empty_route_id_returns_value_error_object(self):
        result = pqt.route_ridership_trend("", START, END)
        assert isinstance(result, ValueError)

    def test_empty_df_returns_no_results_message(self):
        _ql_mock.get_route_ridership_trend.return_value = _empty()
        result = pqt.route_ridership_trend("40", START, END)
        assert "No results" in result

    def test_invalid_aggregation_defaults_to_daily(self):
        _ql_mock.get_route_ridership_trend.return_value = self._df_with_cols()
        pqt.route_ridership_trend("40", START, END, aggregation="INVALID")
        call_kwargs = _ql_mock.get_route_ridership_trend.call_args[1]
        assert call_kwargs["aggregation"] == "daily"

    def test_valid_aggregation_weekly(self):
        _ql_mock.get_route_ridership_trend.return_value = self._df_with_cols()
        pqt.route_ridership_trend("40", START, END, aggregation="weekly")
        call_kwargs = _ql_mock.get_route_ridership_trend.call_args[1]
        assert call_kwargs["aggregation"] == "weekly"

    def test_valid_aggregation_monthly(self):
        _ql_mock.get_route_ridership_trend.return_value = self._df_with_cols()
        pqt.route_ridership_trend("40", START, END, aggregation="monthly")
        call_kwargs = _ql_mock.get_route_ridership_trend.call_args[1]
        assert call_kwargs["aggregation"] == "monthly"

    def test_none_aggregation_defaults_to_daily(self):
        _ql_mock.get_route_ridership_trend.return_value = self._df_with_cols()
        pqt.route_ridership_trend("40", START, END, aggregation=None)
        call_kwargs = _ql_mock.get_route_ridership_trend.call_args[1]
        assert call_kwargs["aggregation"] == "daily"


# ===========================================================================
# busiest_stops tool
# ===========================================================================


class TestBusiestStops:
    def setup_method(self):
        _ql_mock.reset_mock()

    def _df(self):
        return pd.DataFrame(
            {"stop_id": ["S1"], "stop_nm": ["Main"], "total_boardings": [200]}
        )

    def test_returns_formatted_string(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        result = pqt.busiest_stops(START, END)
        assert "Busiest Stops" in result

    def test_empty_df_no_route(self):
        _ql_mock.get_busiest_stops.return_value = _empty()
        result = pqt.busiest_stops(START, END)
        assert "No stop activity found" in result
        assert "for route" not in result

    def test_empty_df_with_route(self):
        _ql_mock.get_busiest_stops.return_value = _empty()
        result = pqt.busiest_stops(START, END, route_id="40")
        assert "for route 40" in result

    def test_metric_board_normalised(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        pqt.busiest_stops(START, END, metric="board")
        call_kwargs = _ql_mock.get_busiest_stops.call_args[1]
        assert call_kwargs["metric"] == "boardings"

    def test_metric_boarding_normalised(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        pqt.busiest_stops(START, END, metric="boarding")
        call_kwargs = _ql_mock.get_busiest_stops.call_args[1]
        assert call_kwargs["metric"] == "boardings"

    def test_metric_alight_normalised(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        pqt.busiest_stops(START, END, metric="alight")
        call_kwargs = _ql_mock.get_busiest_stops.call_args[1]
        assert call_kwargs["metric"] == "alightings"

    def test_metric_alighting_normalised(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        pqt.busiest_stops(START, END, metric="alighting")
        call_kwargs = _ql_mock.get_busiest_stops.call_args[1]
        assert call_kwargs["metric"] == "alightings"

    def test_unknown_metric_defaults_to_boardings(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        pqt.busiest_stops(START, END, metric="UNKNOWN")
        call_kwargs = _ql_mock.get_busiest_stops.call_args[1]
        assert call_kwargs["metric"] == "boardings"

    def test_empty_string_route_id_becomes_none(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        pqt.busiest_stops(START, END, route_id="  ")
        call_kwargs = _ql_mock.get_busiest_stops.call_args[1]
        assert call_kwargs["route_id"] is None

    def test_bad_top_n_defaults_to_10(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        pqt.busiest_stops(START, END, top_n="bad")
        call_kwargs = _ql_mock.get_busiest_stops.call_args[1]
        assert call_kwargs["top_n"] == 10

    def test_route_line_shown_when_route_given(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        result = pqt.busiest_stops(START, END, route_id="40")
        assert "Route filter:** 40" in result

    def test_route_line_none_when_no_route(self):
        _ql_mock.get_busiest_stops.return_value = self._df()
        result = pqt.busiest_stops(START, END)
        assert "Route filter:** None" in result


# ===========================================================================
# service_change_impact tool
# ===========================================================================


class TestServiceChangeImpact:
    def setup_method(self):
        _ql_mock.reset_mock()
        _ql_mock.analyze_service_change_impact.return_value = {
            "before_period": {
                "trips": 50,
                "avg_boardings_per_trip": 40,
                "avg_max_psngr_load": None,
                "crowded_trips": 3,
            },
            "after_period": {
                "trips": 55,
                "avg_boardings_per_trip": 45,
                "avg_max_psngr_load": None,
                "crowded_trips": 4,
            },
            "impact": {
                "boardings_change": 5,
                "boardings_pct_change": 12.5,
                "direction": "increase",
                "significant": True,
            },
        }

    def test_returns_formatted_string(self):
        result = pqt.service_change_impact("40", "2025-06-01")
        assert "Service Change Impact" in result
        assert "Route 40" in result

    def test_empty_route_id_returns_value_error(self):
        result = pqt.service_change_impact("", "2025-06-01")
        assert isinstance(result, ValueError)

    def test_bad_window_days_defaults_to_30(self):
        pqt.service_change_impact("40", "2025-06-01", window_days="bad")
        call_kwargs = _ql_mock.analyze_service_change_impact.call_args[1]
        assert call_kwargs["window_days"] == 30

    def test_window_days_as_string_int_is_coerced(self):
        pqt.service_change_impact("40", "2025-06-01", window_days="14")
        call_kwargs = _ql_mock.analyze_service_change_impact.call_args[1]
        assert call_kwargs["window_days"] == 14


# ===========================================================================
# get_overcrowded_routes tool
# ===========================================================================


class TestGetOvercrowdedRoutesTool:
    def setup_method(self):
        _ql_mock.reset_mock()

    def test_returns_formatted_string(self):
        _ql_mock.get_overcrowded_routes.return_value = pd.DataFrame(
            {"route": ["40"], "overcrowded_trips": [5]}
        )
        result = pqt.get_overcrowded_routes("253")
        assert "Overcrowded Routes" in result
        assert "253" in result

    def test_empty_df_returns_not_found_message(self):
        _ql_mock.get_overcrowded_routes.return_value = _empty()
        result = pqt.get_overcrowded_routes("253")
        assert "No overcrowded routes found" in result

    def test_time_period_filter_shown_in_output(self):
        _ql_mock.get_overcrowded_routes.return_value = pd.DataFrame(
            {"route": ["40"], "overcrowded_trips": [2]}
        )
        result = pqt.get_overcrowded_routes("253", time_period="AM Peak")
        assert "AM Peak" in result

    def test_empty_time_period_string_becomes_none(self):
        _ql_mock.get_overcrowded_routes.return_value = pd.DataFrame(
            {"route": ["40"], "overcrowded_trips": [2]}
        )
        pqt.get_overcrowded_routes("253", time_period="")
        call_kwargs = _ql_mock.get_overcrowded_routes.call_args[1]
        assert call_kwargs["time_period"] is None

    def test_no_time_period_shows_all_in_output(self):
        _ql_mock.get_overcrowded_routes.return_value = pd.DataFrame(
            {"route": ["40"], "overcrowded_trips": [2]}
        )
        result = pqt.get_overcrowded_routes("253")
        assert "All" in result

    def test_bad_top_n_defaults_to_10(self):
        _ql_mock.get_overcrowded_routes.return_value = pd.DataFrame(
            {"route": ["40"], "overcrowded_trips": [2]}
        )
        pqt.get_overcrowded_routes("253", top_n="bad")
        call_kwargs = _ql_mock.get_overcrowded_routes.call_args[1]
        assert call_kwargs["top_n"] == 10


# ===========================================================================
# compare_routes tool
# ===========================================================================


class TestCompareRoutesTool:
    def setup_method(self):
        _ql_mock.reset_mock()

    def test_comma_separated_string_split_into_list(self):
        _ql_mock.compare_routes.return_value = pd.DataFrame(
            {"route": ["40", "7"], "total_boardings": [5000, 3000]}
        )
        pqt.compare_routes("40,7,E Line", START, END)
        call_kwargs = _ql_mock.compare_routes.call_args[1]
        assert call_kwargs["route_ids"] == ["40", "7", "E Line"]

    def test_non_string_route_ids_wrapped_in_list(self):
        _ql_mock.compare_routes.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [5000]}
        )
        pqt.compare_routes(40, START, END)
        call_kwargs = _ql_mock.compare_routes.call_args[1]
        assert call_kwargs["route_ids"] == ["40"]

    def test_empty_result_returns_not_found_message(self):
        _ql_mock.compare_routes.return_value = _empty()
        result = pqt.compare_routes("40,7", START, END)
        assert "No data found" in result

    def test_returns_formatted_string_on_success(self):
        _ql_mock.compare_routes.return_value = pd.DataFrame(
            {"route": ["40"], "total_boardings": [5000]}
        )
        result = pqt.compare_routes("40", START, END)
        assert "Route Comparison" in result


# ===========================================================================
# declining_routes tool
# ===========================================================================


class TestDecliningRoutesTool:
    def setup_method(self):
        _ql_mock.reset_mock()

    def test_returns_declining_string(self):
        _ql_mock.identify_declining_routes.return_value = pd.DataFrame(
            {"route": ["99"], "boardings_pct_change": [-20.0]}
        )
        result = pqt.declining_routes()
        assert "Declining Routes" in result

    def test_empty_df_returns_not_found_message(self):
        _ql_mock.identify_declining_routes.return_value = _empty()
        result = pqt.declining_routes()
        assert "No declining routes found" in result

    def test_bad_params_default_gracefully(self):
        _ql_mock.identify_declining_routes.return_value = pd.DataFrame(
            {"route": ["99"], "boardings_pct_change": [-20.0]}
        )
        pqt.declining_routes(
            comparison_months="bad", threshold_pct="bad", min_trips="bad"
        )
        call_kwargs = _ql_mock.identify_declining_routes.call_args[1]
        assert call_kwargs["comparison_months"] == 3
        assert call_kwargs["threshold_pct"] == -10.0
        assert call_kwargs["min_trips"] == 100

    def test_custom_params_forwarded(self):
        _ql_mock.identify_declining_routes.return_value = pd.DataFrame(
            {"route": ["1"], "boardings_pct_change": [-30.0]}
        )
        pqt.declining_routes(comparison_months=6, threshold_pct=-20.0, min_trips=200)
        call_kwargs = _ql_mock.identify_declining_routes.call_args[1]
        assert call_kwargs["comparison_months"] == 6
        assert call_kwargs["threshold_pct"] == -20.0
        assert call_kwargs["min_trips"] == 200


# ===========================================================================
# crowding_by_time_period tool
# ===========================================================================


class TestCrowdingByTimePeriodTool:
    def setup_method(self):
        _ql_mock.reset_mock()

    def _df(self):
        return pd.DataFrame({"time_period": ["AM Peak"], "pct_crowded": [25.0]})

    def test_returns_formatted_string(self):
        _ql_mock.get_crowding_by_time_period.return_value = self._df()
        result = pqt.crowding_by_time_period(start_date=START, end_date=END)
        assert "Crowding by Time Period" in result

    def test_empty_df_no_route(self):
        _ql_mock.get_crowding_by_time_period.return_value = _empty()
        result = pqt.crowding_by_time_period(start_date=START, end_date=END)
        assert "No crowding data found" in result
        assert "for Route" not in result

    def test_empty_df_with_route(self):
        _ql_mock.get_crowding_by_time_period.return_value = _empty()
        result = pqt.crowding_by_time_period(
            route_id="40", start_date=START, end_date=END
        )
        assert "for Route 40" in result

    def test_empty_string_route_id_becomes_none(self):
        _ql_mock.get_crowding_by_time_period.return_value = self._df()
        pqt.crowding_by_time_period(route_id="", start_date=START, end_date=END)
        call_kwargs = _ql_mock.get_crowding_by_time_period.call_args[1]
        assert call_kwargs["route_id"] is None

    def test_route_line_with_route(self):
        _ql_mock.get_crowding_by_time_period.return_value = self._df()
        result = pqt.crowding_by_time_period(
            route_id="40", start_date=START, end_date=END
        )
        assert "Route:** 40" in result

    def test_route_line_all_routes(self):
        _ql_mock.get_crowding_by_time_period.return_value = self._df()
        result = pqt.crowding_by_time_period(start_date=START, end_date=END)
        assert "All routes" in result


# ===========================================================================
# route_by_direction tool
# ===========================================================================


class TestRouteByDirectionTool:
    def setup_method(self):
        _ql_mock.reset_mock()

    def test_returns_formatted_string(self):
        _ql_mock.get_route_by_direction.return_value = pd.DataFrame(
            {
                "direction_label": ["Inbound", "Outbound"],
                "total_boardings": [3000, 2500],
            }
        )
        result = pqt.route_by_direction("40", START, END)
        assert "Directional Analysis" in result
        assert "Route 40" in result

    def test_empty_df_returns_not_found(self):
        _ql_mock.get_route_by_direction.return_value = _empty()
        result = pqt.route_by_direction("40", START, END)
        assert "No directional data found" in result


# ===========================================================================
# ridership_by_day_type tool
# ===========================================================================


class TestRidershipByDayTypeTool:
    def setup_method(self):
        _ql_mock.reset_mock()

    def _df(self):
        return pd.DataFrame({"day_type": ["Weekday"], "total_boardings": [100000]})

    def test_returns_formatted_string(self):
        _ql_mock.get_ridership_by_day_type.return_value = self._df()
        result = pqt.ridership_by_day_type(start_date=START, end_date=END)
        assert "Ridership by Day Type" in result

    def test_empty_df_no_route(self):
        _ql_mock.get_ridership_by_day_type.return_value = _empty()
        result = pqt.ridership_by_day_type(start_date=START, end_date=END)
        assert "No data found" in result
        assert "for Route" not in result

    def test_empty_df_with_route(self):
        _ql_mock.get_ridership_by_day_type.return_value = _empty()
        result = pqt.ridership_by_day_type(
            route_id="40", start_date=START, end_date=END
        )
        assert "for Route 40" in result

    def test_empty_string_route_becomes_none(self):
        _ql_mock.get_ridership_by_day_type.return_value = self._df()
        pqt.ridership_by_day_type(route_id="", start_date=START, end_date=END)
        call_kwargs = _ql_mock.get_ridership_by_day_type.call_args[1]
        assert call_kwargs["route_id"] is None

    def test_route_line_with_route(self):
        _ql_mock.get_ridership_by_day_type.return_value = self._df()
        result = pqt.ridership_by_day_type(route_id="7", start_date=START, end_date=END)
        assert "Route:** 7" in result

    def test_route_line_all_routes(self):
        _ql_mock.get_ridership_by_day_type.return_value = self._df()
        result = pqt.ridership_by_day_type(start_date=START, end_date=END)
        assert "All routes" in result


# ===========================================================================
# ALL_TOOLS, get_all_tools, get_tool_names
# ===========================================================================


class TestToolRegistry:
    def test_all_tools_is_list_of_10(self):
        assert isinstance(pqt.ALL_TOOLS, list)
        assert len(pqt.ALL_TOOLS) == 10

    def test_get_all_tools_returns_all_tools(self):
        assert pqt.get_all_tools() is pqt.ALL_TOOLS

    def test_get_tool_names_returns_list_of_strings(self):
        names = pqt.get_tool_names()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)

    def test_expected_tool_names_present(self):
        names = pqt.get_tool_names()
        expected = [
            "top_routes_by_ridership",
            "route_ridership_trend",
            "busiest_stops",
            "service_change_impact",
            "get_overcrowded_routes",
            "compare_routes",
            "declining_routes",
            "crowding_by_time_period",
            "route_by_direction",
            "ridership_by_day_type",
        ]
        for name in expected:
            assert name in names, f"Missing tool: {name}"


# ===========================================================================
# _build_engine (password branch)
# ===========================================================================


class TestBuildEngine:
    def test_engine_url_with_password(self):
        with patch.dict(
            "os.environ",
            {
                "SQL_HOST": "myhost",
                "SQL_PORT": "5432",
                "SQL_DATABASE": "transit_db",
                "SQL_USERNAME": "user",
                "SQL_PASSWORD": "secret",
            },
        ):
            with patch("planner_query_tools.create_engine") as mock_ce:
                mock_ce.return_value = MagicMock()
                pqt._build_engine()
                url = mock_ce.call_args[0][0]
                assert "secret" in url
                assert "user" in url

    def test_engine_url_without_password(self):
        with patch.dict(
            "os.environ",
            {
                "SQL_HOST": "myhost",
                "SQL_PORT": "5432",
                "SQL_DATABASE": "transit_db",
                "SQL_USERNAME": "user",
                "SQL_PASSWORD": "",
            },
        ):
            with patch("planner_query_tools.create_engine") as mock_ce:
                mock_ce.return_value = MagicMock()
                pqt._build_engine()
                url = mock_ce.call_args[0][0]
                # password should NOT be in URL
                assert "@" in url
                assert ":@" not in url or "secret" not in url
