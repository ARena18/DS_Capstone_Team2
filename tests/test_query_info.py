# tests/test_query_info.py
# 100% coverage for updated_combined/query_info.py
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest  # noqa: F401  (used implicitly via capsys fixture)

# ── 1. Path setup FIRST ───────────────────────────────────────────────────────
_TESTS_DIR = os.path.dirname(__file__)
_PROJECT_DIR = os.path.dirname(_TESTS_DIR)
COMBINED_DIR = os.path.join(_PROJECT_DIR, "updated_combined")
if COMBINED_DIR not in sys.path:
    sys.path.insert(0, COMBINED_DIR)

# ── 2. Clean stale modules ────────────────────────────────────────────────────
for _k in list(sys.modules.keys()):
    if any(_k.startswith(p) for p in ("query_info", "psycopg2", "dotenv")):
        sys.modules.pop(_k, None)

# ── 3. psycopg2 stub ─────────────────────────────────────────────────────────
_psycopg2 = types.ModuleType("psycopg2")
_psycopg2.connect = MagicMock()
_psycopg2.Error = Exception
sys.modules["psycopg2"] = _psycopg2

# ── 4. dotenv stub ────────────────────────────────────────────────────────────
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda: None
sys.modules["dotenv"] = _dotenv

# ── 5. Import the real module ─────────────────────────────────────────────────
import query_info as qi  # noqa: E402


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_mock_connect(rows):
    """Return a (mock_connect, mock_cur) pair.

    mock_connect behaves as a context manager yielding a connection whose
    cursor() is also a context manager yielding mock_cur.
    mock_cur.fetchall() returns `rows`.
    """
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = rows

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_connect = MagicMock()
    mock_connect.return_value.__enter__ = lambda s: mock_conn
    mock_connect.return_value.__exit__ = MagicMock(return_value=False)

    return mock_connect, mock_cur


# =============================================================================
# TestModuleConstants
# Importing qi executes all module-level lines: SCHEMA, OLD_SCHEMA, db_params.
# =============================================================================

class TestModuleConstants:
    def test_schema_is_string(self):
        assert isinstance(qi.SCHEMA, str)

    def test_schema_contains_trips_table(self):
        assert "CREATE TABLE trips" in qi.SCHEMA

    def test_schema_contains_stop_daily_table(self):
        assert "CREATE TABLE stop_daily" in qi.SCHEMA

    def test_schema_contains_stops_reference_table(self):
        assert "CREATE TABLE stops_reference" in qi.SCHEMA

    def test_old_schema_is_string(self):
        assert isinstance(qi.OLD_SCHEMA, str)

    def test_old_schema_contains_trips_table(self):
        assert "CREATE TABLE trips" in qi.OLD_SCHEMA

    def test_old_schema_contains_view(self):
        assert "CREATE OR REPLACE VIEW" in qi.OLD_SCHEMA

    def test_db_params_is_dict(self):
        assert isinstance(qi.db_params, dict)

    def test_db_params_has_host_key(self):
        assert "host" in qi.db_params

    def test_db_params_has_database_key(self):
        assert "database" in qi.db_params

    def test_db_params_has_user_key(self):
        assert "user" in qi.db_params

    def test_db_params_has_password_key(self):
        assert "password" in qi.db_params

    def test_db_params_has_port_key(self):
        assert "port" in qi.db_params


# =============================================================================
# TestQueryDb
# Covers both branches of query_db(): success path and exception path.
# =============================================================================

class TestQueryDb:
    def test_returns_rows_on_success(self):
        rows = [("Route 40", 1000), ("Route 7", 800)]
        mock_connect, _ = _make_mock_connect(rows)

        with patch.object(qi, "psycopg2") as mock_pg:
            mock_pg.connect = mock_connect
            mock_pg.Error = Exception
            result = qi.query_db("SELECT * FROM trips")

        assert result == rows

    def test_returns_empty_list_when_no_rows(self):
        mock_connect, _ = _make_mock_connect([])

        with patch.object(qi, "psycopg2") as mock_pg:
            mock_pg.connect = mock_connect
            mock_pg.Error = Exception
            result = qi.query_db("SELECT * FROM trips WHERE 1=0")

        assert result == []

    def test_execute_called_with_query(self):
        mock_connect, mock_cur = _make_mock_connect([("x",)])

        with patch.object(qi, "psycopg2") as mock_pg:
            mock_pg.connect = mock_connect
            mock_pg.Error = Exception
            qi.query_db("SELECT 1")

        mock_cur.execute.assert_called_once_with("SELECT 1")

    def test_prints_connected_on_success(self, capsys):
        mock_connect, _ = _make_mock_connect([])

        with patch.object(qi, "psycopg2") as mock_pg:
            mock_pg.connect = mock_connect
            mock_pg.Error = Exception
            qi.query_db("SELECT 1")

        assert "Connected" in capsys.readouterr().out

    def test_returns_error_string_on_exception(self):
        with patch.object(qi, "psycopg2") as mock_pg:
            mock_pg.connect.side_effect = Exception("connection refused")
            mock_pg.Error = Exception
            result = qi.query_db("SELECT 1")

        assert isinstance(result, str)
        assert "Error" in result

    def test_error_string_contains_exception_message(self):
        with patch.object(qi, "psycopg2") as mock_pg:
            mock_pg.connect.side_effect = Exception("timeout occurred")
            mock_pg.Error = Exception
            result = qi.query_db("SELECT 1")

        assert "timeout occurred" in result

    def test_prints_error_on_exception(self, capsys):
        with patch.object(qi, "psycopg2") as mock_pg:
            mock_pg.connect.side_effect = Exception("fail")
            mock_pg.Error = Exception
            qi.query_db("SELECT 1")

        assert "Error" in capsys.readouterr().out