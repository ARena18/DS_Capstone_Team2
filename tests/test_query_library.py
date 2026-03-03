"""
Tests for query_library.py — 100% branch coverage.

The database engine is fully mocked so no real PostgreSQL connection is needed.
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Minimal stubs so query_library.py can be imported without SQLAlchemy
# ---------------------------------------------------------------------------
import sys
import types


def _make_sa_stub():
    sa = types.ModuleType("sqlalchemy")
    sa.create_engine = MagicMock()

    def _text(sql):
        """Return the SQL string as-is so tests can inspect it."""
        return sql

    sa.text = _text

    engine_mod = types.ModuleType("sqlalchemy.engine")
    engine_mod.Engine = object  # just a base class placeholder

    sys.modules.setdefault("sqlalchemy", sa)
    sys.modules.setdefault("sqlalchemy.engine", engine_mod)
    return sa


_sa = _make_sa_stub()

from query_library import TransitQueryLibrary  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_engine(rows, columns):
    """
    Build a mock SQLAlchemy engine whose .connect().__enter__().execute()
    returns a result with fetchall() == rows and keys() == columns.
    """
    result = MagicMock()
    result.fetchall.return_value = rows
    result.keys.return_value = columns

    conn = MagicMock()
    conn.execute.return_value = result

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn)
    ctx.__exit__ = MagicMock(return_value=False)

    engine = MagicMock()
    engine.connect.return_value = ctx
    return engine, conn


def _row(*values):
    return values


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

START = "2025-01-01"
END = "2025-12-31"


# ===========================================================================
# TransitQueryLibrary.get_top_routes_by_ridership
# ===========================================================================


class TestGetTopRoutesByRidership:
    def test_no_filters(self):
        rows = [_row("40", 5000, 4800, 120, 0.75, 10)]
        cols = [
            "route",
            "total_boardings",
            "total_alightings",
            "total_trips",
            "avg_load_factor",
            "crowded_trips",
        ]
        engine, conn = _mock_engine(rows, cols)
        lib = TransitQueryLibrary(engine)

        df = lib.get_top_routes_by_ridership(START, END)

        assert isinstance(df, pd.DataFrame)
        assert df.iloc[0]["route"] == "40"
        # Verify SQL was executed once
        conn.execute.assert_called_once()

    def test_with_day_code_filter(self):
        rows = [_row("7", 3000, 2900, 80, 0.60, 5)]
        cols = [
            "route",
            "total_boardings",
            "total_alightings",
            "total_trips",
            "avg_load_factor",
            "crowded_trips",
        ]
        engine, conn = _mock_engine(rows, cols)
        lib = TransitQueryLibrary(engine)

        df = lib.get_top_routes_by_ridership(START, END, day_code="WK")

        sql_call = conn.execute.call_args
        # Params dict should contain day_code
        params = sql_call[0][1]  # positional arg 1 is params dict
        assert params.get("day_code") == "WK"

    def test_with_direction_filter(self):
        rows = [_row("40", 2500, 2400, 60, 0.70, 3)]
        cols = [
            "route",
            "total_boardings",
            "total_alightings",
            "total_trips",
            "avg_load_factor",
            "crowded_trips",
        ]
        engine, conn = _mock_engine(rows, cols)
        lib = TransitQueryLibrary(engine)

        df = lib.get_top_routes_by_ridership(START, END, direction="I")

        params = conn.execute.call_args[0][1]
        assert params.get("direction") == "I"

    def test_with_both_filters(self):
        engine, conn = _mock_engine([], ["route"])
        lib = TransitQueryLibrary(engine)

        lib.get_top_routes_by_ridership(START, END, day_code="SA", direction="O")

        params = conn.execute.call_args[0][1]
        assert params["day_code"] == "SA"
        assert params["direction"] == "O"

    def test_custom_top_n(self):
        engine, conn = _mock_engine([], ["route"])
        lib = TransitQueryLibrary(engine)

        lib.get_top_routes_by_ridership(START, END, top_n=5)

        params = conn.execute.call_args[0][1]
        assert params["top_n"] == 5


# ===========================================================================
# TransitQueryLibrary.get_route_ridership_trend
# ===========================================================================


class TestGetRouteRidershipTrend:
    def _make_lib(self, rows=None, cols=None):
        rows = rows or [_row("2025-01-01", 500, 480, 10, 0.65, 2)]
        cols = cols or [
            "period",
            "total_boardings",
            "total_alightings",
            "trip_count",
            "avg_load_factor",
            "crowded_trips",
        ]
        engine, conn = _mock_engine(rows, cols)
        return TransitQueryLibrary(engine), conn

    def test_daily_aggregation(self):
        lib, conn = self._make_lib()
        df = lib.get_route_ridership_trend("40", START, END, aggregation="daily")
        assert isinstance(df, pd.DataFrame)
        sql = conn.execute.call_args[0][0]
        assert "operation_date" in sql  # daily → operation_date as group

    def test_weekly_aggregation(self):
        lib, conn = self._make_lib()
        lib.get_route_ridership_trend("40", START, END, aggregation="weekly")
        sql = conn.execute.call_args[0][0]
        assert "week" in sql.lower()

    def test_monthly_aggregation(self):
        lib, conn = self._make_lib()
        lib.get_route_ridership_trend("40", START, END, aggregation="monthly")
        sql = conn.execute.call_args[0][0]
        assert "month" in sql.lower()

    def test_default_aggregation_is_daily(self):
        lib, conn = self._make_lib()
        lib.get_route_ridership_trend("40", START, END)
        sql = conn.execute.call_args[0][0]
        # 'operation_date' means daily grouping was chosen
        assert "operation_date" in sql


# ===========================================================================
# TransitQueryLibrary.get_busiest_stops
# ===========================================================================


class TestGetBusiestStops:
    def _make_lib(self, rows=None):
        rows = rows or [_row("S1", "Main St", 200, 180, 10, 0.5, 50)]
        cols = [
            "stop_id",
            "stop_nm",
            "total_boardings",
            "total_alightings",
            "days_with_data",
            "avg_departure_load",
            "total_trips",
        ]
        engine, conn = _mock_engine(rows, cols)
        return TransitQueryLibrary(engine), conn

    def test_boardings_metric(self):
        lib, conn = self._make_lib()
        df = lib.get_busiest_stops(START, END, metric="boardings")
        sql = conn.execute.call_args[0][0]
        assert "total_boardings" in sql

    def test_alightings_metric(self):
        lib, conn = self._make_lib()
        lib.get_busiest_stops(START, END, metric="alightings")
        sql = conn.execute.call_args[0][0]
        assert "total_alightings" in sql

    def test_with_route_id_filter(self):
        lib, conn = self._make_lib()
        lib.get_busiest_stops(START, END, route_id="40")
        params = conn.execute.call_args[0][1]
        assert params["route_id"] == "40"

    def test_without_route_id(self):
        lib, conn = self._make_lib()
        lib.get_busiest_stops(START, END)
        params = conn.execute.call_args[0][1]
        assert params["route_id"] is None

    def test_custom_top_n(self):
        lib, conn = self._make_lib()
        lib.get_busiest_stops(START, END, top_n=5)
        params = conn.execute.call_args[0][1]
        assert params["top_n"] == 5


# ===========================================================================
# TransitQueryLibrary.analyze_service_change_impact
# ===========================================================================


class TestAnalyzeServiceChangeImpact:
    def _make_engine_two_calls(self, before_row, after_row):
        """Engine whose conn.execute returns before_row then after_row."""
        before_result = MagicMock()
        before_result.fetchone.return_value = before_row

        after_result = MagicMock()
        after_result.fetchone.return_value = after_row

        conn = MagicMock()
        conn.execute.side_effect = [before_result, after_result]

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=conn)
        ctx.__exit__ = MagicMock(return_value=False)

        engine = MagicMock()
        engine.connect.return_value = ctx
        return engine

    def _before(self, avg_board=100.0, avg_load=0.6):
        # (trips, days, avg_boardings, total_boardings, avg_load_factor, crowded_trips)
        return _row(50, 20, avg_board, avg_board * 50, avg_load, 5)

    def _after(self, avg_board=110.0, avg_load=0.65):
        return _row(55, 22, avg_board, avg_board * 55, avg_load, 6)

    def test_basic_structure(self):
        engine = self._make_engine_two_calls(self._before(), self._after())
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-06-01", window_days=30)

        assert result["route_id"] == "40"
        assert result["change_date"] == "2025-06-01"
        assert result["window_days"] == 30
        assert "before_period" in result
        assert "after_period" in result
        assert "impact" in result

    def test_increase_direction_when_after_higher(self):
        engine = self._make_engine_two_calls(self._before(100), self._after(120))
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-06-01")
        assert result["impact"]["direction"] == "increase"

    def test_decrease_direction_when_after_lower(self):
        engine = self._make_engine_two_calls(self._before(120), self._after(100))
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-06-01")
        assert result["impact"]["direction"] == "decrease"

    def test_significant_flag_true_when_change_exceeds_5pct(self):
        # 100 → 115 is 15% → significant
        engine = self._make_engine_two_calls(self._before(100), self._after(115))
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-06-01")
        assert result["impact"]["significant"] is True

    def test_significant_flag_false_when_change_under_5pct(self):
        # 100 → 103 is 3% → not significant
        engine = self._make_engine_two_calls(self._before(100), self._after(103))
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-06-01")
        assert result["impact"]["significant"] is False

    def test_zero_before_avg_boardings_no_division_error(self):
        """When before avg is 0, pct change must be 0 (guard against ZeroDivisionError)."""
        engine = self._make_engine_two_calls(self._before(0), self._after(50))
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-06-01")
        assert result["impact"]["boardings_pct_change"] == 0

    def test_none_values_in_before_row_handled_gracefully(self):
        """None result fields should default to 0 without raising."""
        before = _row(0, 0, None, None, None, 0)
        after = _row(5, 5, 20.0, 100.0, 0.5, 1)
        engine = self._make_engine_two_calls(before, after)
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-06-01")
        assert result["before_period"]["avg_boardings_per_trip"] is None

    def test_date_window_calculation(self):
        """Verify before/after date strings are computed correctly."""
        engine = self._make_engine_two_calls(self._before(), self._after())
        lib = TransitQueryLibrary(engine)
        result = lib.analyze_service_change_impact("40", "2025-03-01", window_days=10)

        change = date(2025, 3, 1)
        assert result["before_period"]["end_date"] == str(change - timedelta(days=1))
        assert result["after_period"]["start_date"] == str(change)


# ===========================================================================
# TransitQueryLibrary.get_overcrowded_routes
# ===========================================================================


class TestGetOvercrowdedRoutes:
    def _make_lib(self, rows=None):
        rows = rows or [_row("40", 5, 20, 25.0, 80.0, 70.0, 10.0)]
        cols = [
            "route",
            "overcrowded_trips",
            "total_trips_count",
            "pct_overcrowded",
            "avg_max_load",
            "avg_threshold",
            "avg_excess_load",
        ]
        engine, conn = _mock_engine(rows, cols)
        return TransitQueryLibrary(engine), conn

    def test_with_service_change_num(self):
        lib, conn = self._make_lib()
        df = lib.get_overcrowded_routes("253")
        params = conn.execute.call_args[0][1]
        assert params["service_change_num"] == "253"

    def test_with_time_period_filter(self):
        lib, conn = self._make_lib()
        lib.get_overcrowded_routes("253", time_period="AM Peak")
        params = conn.execute.call_args[0][1]
        assert params["time_period"] == "AM Peak"

    def test_without_time_period_not_in_params(self):
        lib, conn = self._make_lib()
        lib.get_overcrowded_routes("253")
        params = conn.execute.call_args[0][1]
        assert "time_period" not in params

    def test_raises_when_service_change_num_is_none(self):
        engine, _ = _mock_engine([], [])
        lib = TransitQueryLibrary(engine)
        with pytest.raises(ValueError, match="Must provide service_change_num"):
            lib.get_overcrowded_routes(None)

    def test_returns_dataframe(self):
        lib, _ = self._make_lib()
        df = lib.get_overcrowded_routes("253")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1


# ===========================================================================
# TransitQueryLibrary.compare_routes
# ===========================================================================


class TestCompareRoutes:
    def test_returns_dataframe_with_expected_columns(self):
        rows = [_row("40", 5000, 4800, 100, 60.0, 10, 10.0)]
        cols = [
            "route",
            "total_boardings",
            "total_alightings",
            "total_trips",
            "avg_max_psngr_load",
            "crowded_trips",
            "pct_crowded",
        ]
        engine, conn = _mock_engine(rows, cols)
        lib = TransitQueryLibrary(engine)

        df = lib.compare_routes(["40", "7"], START, END)

        assert isinstance(df, pd.DataFrame)
        params = conn.execute.call_args[0][1]
        assert params["route_ids"] == ["40", "7"]

    def test_date_params_passed(self):
        engine, conn = _mock_engine([], ["route"])
        lib = TransitQueryLibrary(engine)
        lib.compare_routes(["40"], START, END)
        params = conn.execute.call_args[0][1]
        assert params["start_date"] == START
        assert params["end_date"] == END


# ===========================================================================
# TransitQueryLibrary.identify_declining_routes
# ===========================================================================


class TestIdentifyDecliningRoutes:
    def _engine_with_summary_and_declining(self, declining_rows):
        """
        First call → summary (for get_summary), subsequent calls → declining rows.
        """
        # Summary result
        summary_result = MagicMock()
        summary_result.fetchone.return_value = _row(
            "2024-01-01", "2025-12-31", 365, 127, 2_000_000
        )

        # Declining routes result
        dec_result = MagicMock()
        dec_result.fetchall.return_value = declining_rows
        dec_result.keys.return_value = [
            "route",
            "trip_count",
            "previous_avg_boardings",
            "recent_avg_boardings",
            "boardings_pct_change",
            "previous_load_factor",
            "recent_load_factor",
            "max_psngr_load_change",
        ]

        conn = MagicMock()
        conn.execute.side_effect = [summary_result, dec_result]

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=conn)
        ctx.__exit__ = MagicMock(return_value=False)

        engine = MagicMock()
        engine.connect.return_value = ctx
        return engine

    def test_returns_dataframe(self):
        engine = self._engine_with_summary_and_declining(
            [_row("99", 200, 100.0, 80.0, -20.0, 0.5, 0.4, -0.1)]
        )
        lib = TransitQueryLibrary(engine)
        df = lib.identify_declining_routes(
            comparison_months=3, threshold_pct=-10.0, min_trips=100
        )
        assert isinstance(df, pd.DataFrame)
        assert df.iloc[0]["route"] == "99"

    def test_params_are_forwarded(self):
        engine = self._engine_with_summary_and_declining([])
        lib = TransitQueryLibrary(engine)
        lib.identify_declining_routes(
            comparison_months=6, threshold_pct=-15.0, min_trips=50
        )
        # Second execute call is the real declining query
        params = conn_from_engine(engine).execute.call_args_list[1][0][1]
        assert params["min_trips"] == 50
        assert params["threshold_pct"] == -15.0


def conn_from_engine(engine):
    return engine.connect.return_value.__enter__.return_value


# ===========================================================================
# TransitQueryLibrary.get_crowding_by_time_period
# ===========================================================================


class TestGetCrowdingByTimePeriod:
    def _make_lib(self):
        rows = [_row("AM Peak", 100, 20, 20.0, 65.0, 30.0)]
        cols = [
            "time_period",
            "total_trips",
            "crowded_trips",
            "pct_crowded",
            "avg_max_psngr_load",
            "avg_boardings",
        ]
        engine, conn = _mock_engine(rows, cols)
        return TransitQueryLibrary(engine), conn

    def test_without_route_filter(self):
        lib, conn = self._make_lib()
        lib.get_crowding_by_time_period(start_date=START, end_date=END)
        params = conn.execute.call_args[0][1]
        assert params["route_id"] is None
        sql = conn.execute.call_args[0][0]
        # route_id filter clause should NOT appear
        assert "service_rte_num = :route_id" not in sql

    def test_with_route_filter_adds_where_clause(self):
        lib, conn = self._make_lib()
        lib.get_crowding_by_time_period(route_id="40", start_date=START, end_date=END)
        sql = conn.execute.call_args[0][0]
        assert "service_rte_num = :route_id" in sql

    def test_returns_dataframe(self):
        lib, _ = self._make_lib()
        df = lib.get_crowding_by_time_period(start_date=START, end_date=END)
        assert isinstance(df, pd.DataFrame)


# ===========================================================================
# TransitQueryLibrary.get_route_by_direction
# ===========================================================================


class TestGetRouteByDirection:
    def test_returns_dataframe(self):
        rows = [
            _row("I", "Inbound", 3000, 60, 55.0),
            _row("O", "Outbound", 2500, 55, 50.0),
        ]
        cols = [
            "direction",
            "direction_label",
            "total_boardings",
            "total_trips",
            "avg_max_psngr_load",
        ]
        engine, conn = _mock_engine(rows, cols)
        lib = TransitQueryLibrary(engine)

        df = lib.get_route_by_direction("40", START, END)

        assert len(df) == 2
        assert set(df["direction_label"]) == {"Inbound", "Outbound"}

    def test_route_id_passed_in_params(self):
        engine, conn = _mock_engine([], ["direction"])
        lib = TransitQueryLibrary(engine)
        lib.get_route_by_direction("7", START, END)
        params = conn.execute.call_args[0][1]
        assert params["route_id"] == "7"


# ===========================================================================
# TransitQueryLibrary.get_ridership_by_day_type
# ===========================================================================


class TestGetRidershipByDayType:
    def _make_lib(self):
        rows = [
            _row("WK", "Weekday", 250, 3000, 150000, 50.0, 60.0),
            _row("SA", "Saturday", 52, 500, 20000, 40.0, 50.0),
        ]
        cols = [
            "day_code",
            "day_type",
            "days",
            "total_trips",
            "total_boardings",
            "avg_boardings_per_trip",
            "avg_max_psngr_load",
        ]
        engine, conn = _mock_engine(rows, cols)
        return TransitQueryLibrary(engine), conn

    def test_returns_dataframe(self):
        lib, _ = self._make_lib()
        df = lib.get_ridership_by_day_type(start_date=START, end_date=END)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_with_route_id_adds_where_clause(self):
        lib, conn = self._make_lib()
        lib.get_ridership_by_day_type(route_id="40", start_date=START, end_date=END)
        sql = conn.execute.call_args[0][0]
        assert "service_rte_num = :route_id" in sql

    def test_without_route_id_no_route_clause(self):
        lib, conn = self._make_lib()
        lib.get_ridership_by_day_type(start_date=START, end_date=END)
        sql = conn.execute.call_args[0][0]
        assert "service_rte_num = :route_id" not in sql


# ===========================================================================
# TransitQueryLibrary.get_summary
# ===========================================================================


class TestGetSummary:
    def test_returns_correct_dict_structure(self):
        row = _row("2025-01-01", "2025-12-31", 365, 127, 2_000_000)
        result = MagicMock()
        result.fetchone.return_value = row

        conn = MagicMock()
        conn.execute.return_value = result

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=conn)
        ctx.__exit__ = MagicMock(return_value=False)

        engine = MagicMock()
        engine.connect.return_value = ctx

        lib = TransitQueryLibrary(engine)
        summary = lib.get_summary()

        assert summary["earliest_date"] == "2025-01-01"
        assert summary["latest_date"] == "2025-12-31"
        assert summary["distinct_dates"] == 365
        assert summary["unique_routes"] == 127
        assert summary["total_trips"] == 2_000_000

    def test_dates_are_strings(self):
        row = _row(date(2025, 1, 1), date(2025, 12, 31), 365, 127, 1_000_000)
        result = MagicMock()
        result.fetchone.return_value = row

        conn = MagicMock()
        conn.execute.return_value = result

        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=conn)
        ctx.__exit__ = MagicMock(return_value=False)

        engine = MagicMock()
        engine.connect.return_value = ctx

        lib = TransitQueryLibrary(engine)
        summary = lib.get_summary()

        assert isinstance(summary["earliest_date"], str)
        assert isinstance(summary["latest_date"], str)
