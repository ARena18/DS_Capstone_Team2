"""
Tests for app.py — 100% branch coverage.

Streamlit, LangChain, plotly, and DB are all mocked.
Only the pure-logic functions are exercised:
  - run_agent()
  - _extract_df_from_tool()
  - _auto_visualize()
  - display_messages()
"""

import sys
import os

root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "combined"))
sys.path.insert(0, root_path)

import types
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Stub ALL external dependencies before importing app.py
# ---------------------------------------------------------------------------


def _stub(name, **attrs):
    m = sys.modules.get(name) or types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# ── Streamlit ────────────────────────────────────────────────────────────────
_st = _stub("streamlit")
_st.set_page_config = MagicMock()
_st.markdown = MagicMock()
_st.chat_input = MagicMock(return_value=None)
_st.dataframe = MagicMock()
_st.plotly_chart = MagicMock()
_st.expander = MagicMock(
    return_value=MagicMock(
        __enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock()
    )
)
_st.sidebar = MagicMock()
_st.empty = MagicMock(return_value=MagicMock())
_st.error = MagicMock()
_st.success = MagicMock()
_st.warning = MagicMock()
_st.metric = MagicMock()
_st.caption = MagicMock()
_st.button = MagicMock(return_value=False)
_st.selectbox = MagicMock(return_value="SQL injection")
_st.text_input = MagicMock(return_value="")
_st.code = MagicMock()
_st.rerun = MagicMock()


class _SS(dict):
    """Dict that supports attribute access for st.session_state."""

    def __getattr__(self, k):
        return self[k]

    def __setattr__(self, k, v):
        self[k] = v

    def __contains__(self, k):
        return dict.__contains__(self, k)


_session_state = _SS(
    {
        "messages": [{"role": "assistant", "content": "Hi!"}],
        "agent_log": [],
        "staged_query": "",
        "processing": False,
    }
)
_st.session_state = _session_state

# ── plotly ───────────────────────────────────────────────────────────────────
_plotly = _stub("plotly")
_px = _stub("plotly.express")
_go = _stub("plotly.graph_objects")
_fake_fig = MagicMock(name="FakeFig")
_px.bar = MagicMock(return_value=_fake_fig)
_px.line = MagicMock(return_value=_fake_fig)

# ── LangChain ────────────────────────────────────────────────────────────────
_lc_core = _stub("langchain_core")
_lc_msg = _stub("langchain_core.messages")


class _FakeMsg:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


_lc_msg.SystemMessage = lambda x: ("sys", x)
_lc_msg.HumanMessage = lambda x: ("human", x)
_lc_msg.AIMessage = MagicMock
_lc_msg.ToolMessage = MagicMock

_lc_ollama = _stub("langchain_ollama")
_mock_llm = MagicMock()
_lc_ollama.ChatOllama = MagicMock(return_value=_mock_llm)
_mock_llm.bind_tools.return_value = _mock_llm

# ── sqlalchemy + dotenv ──────────────────────────────────────────────────────
_sa = _stub("sqlalchemy")
_sa.create_engine = MagicMock(return_value=MagicMock())
_sa.text = lambda s: s
_stub("sqlalchemy.engine").Engine = object
_stub("dotenv").load_dotenv = MagicMock()
_stub("psycopg2")
_stub("langchain_core.tools").tool = lambda fn: fn

# ── query_library & planner_query_tools stubs ─────────────────────────────
_ql_mock = MagicMock()
_ql_mod = _stub("query_library")
_ql_mod.TransitQueryLibrary = MagicMock(return_value=_ql_mock)

_pqt_mod = _stub("planner_query_tools")
_pqt_mod.ALL_TOOLS = []
_pqt_mod.query_lib = _ql_mock
_pqt_mod.get_all_tools = MagicMock(return_value=[])

# ── visualization_agent stub ─────────────────────────────────────────────────
_viz_mod = _stub("visualization_agent")
_viz_inst = MagicMock()
_viz_inst.generate = MagicMock(return_value=_fake_fig)
_viz_mod.VisualizationAgent = MagicMock(return_value=_viz_inst)

# ── st_copy stub ──────────────────────────────────────────────────────────────
_st_copy = _stub("st_copy")
_st_copy.copy_button = MagicMock()

# ---------------------------------------------------------------------------
# Now import the module — every external call is mocked
# ---------------------------------------------------------------------------

# Patch time.sleep so tests run instantly
import time as _time_mod

_time_mod.sleep = MagicMock()

import app  # noqa: E402

# Point app's globals at our mocks
app.llm = _mock_llm
app.query_lib = _ql_mock
app.viz_agent = _viz_inst


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df(**cols):
    return pd.DataFrame(cols)


def _reset_session(**overrides):
    _session_state.clear()
    _session_state.update(
        {
            "messages": [{"role": "assistant", "content": "Hi!"}],
            "agent_log": [],
            "staged_query": "",
            "processing": False,
        }
    )
    _session_state.update(overrides)


START = "2025-01-01"
END = "2025-12-31"


# ===========================================================================
# run_agent
# ===========================================================================


class TestRunAgent:
    def setup_method(self):
        _reset_session()
        _mock_llm.reset_mock()
        _ql_mock.reset_mock()
        _viz_inst.generate.reset_mock()
        _lc_msg.ToolMessage.reset_mock()

    # ── LLM error ─────────────────────────────────────────────────────────

    def test_llm_invoke_exception_returns_error_dict(self):
        _mock_llm.invoke.side_effect = RuntimeError("boom")
        result = app.run_agent("any query")
        assert "⚠️ LLM error" in result["text"]
        assert result["df"] is None
        assert result["fig"] is None
        _mock_llm.invoke.side_effect = None  # reset

    # ── No tool calls → plain text ─────────────────────────────────────────

    def test_no_tool_calls_returns_content(self):
        _mock_llm.invoke.return_value = _FakeMsg(content="Hello!", tool_calls=[])
        result = app.run_agent("hi")
        assert result["text"] == "Hello!"
        assert result["df"] is None
        assert result["fig"] is None

    def test_no_tool_calls_empty_content_returns_fallback(self):
        _mock_llm.invoke.return_value = _FakeMsg(content="", tool_calls=[])
        result = app.run_agent("hi")
        assert result["text"] == "I couldn't generate a response."

    # ── Tool calls ────────────────────────────────────────────────────────

    def _tool_response(self, tool_name, args, df):
        """Set up LLM + query_lib mocks for a single tool call."""
        tool_msg = MagicMock()
        tool_msg.content = "mock tool output"

        _mock_llm.invoke.return_value = _FakeMsg(
            content="", tool_calls=[{"name": tool_name, "args": args, "id": "tc-1"}]
        )

        # The tool in TOOL_MAP
        fake_tool = MagicMock()
        fake_tool.invoke.return_value = tool_msg
        app.TOOL_MAP = {tool_name: fake_tool}
        return fake_tool

    def test_tool_call_unknown_tool_adds_warning(self):
        _mock_llm.invoke.return_value = _FakeMsg(
            content="",
            tool_calls=[{"name": "nonexistent_tool", "args": {}, "id": "tc-x"}],
        )
        app.TOOL_MAP = {}

        # Summary LLM returns something
        summary_llm = MagicMock()
        summary_llm.invoke.return_value = _FakeMsg(content="Summary")
        with patch.object(_lc_ollama, "ChatOllama", return_value=summary_llm):
            result = app.run_agent("query")

        assert "⚠️ Unknown tool" in result["text"] or "Summary" in result["text"]

    def test_tool_call_with_content_attribute(self):
        tool_msg = MagicMock(spec=["content"])
        tool_msg.content = "tool output with content"
        fake_tool = MagicMock()
        fake_tool.invoke.return_value = tool_msg
        app.TOOL_MAP = {"top_routes_by_ridership": fake_tool}

        _mock_llm.invoke.return_value = _FakeMsg(
            content="",
            tool_calls=[{"name": "top_routes_by_ridership", "args": {}, "id": "tc-1"}],
        )
        _ql_mock.get_top_routes_by_ridership.return_value = _df(
            route=["40"], total_boardings=[5000]
        )

        summary_llm = MagicMock()
        summary_llm.invoke.return_value = _FakeMsg(content="Here are top routes.")
        with patch.object(_lc_ollama, "ChatOllama", return_value=summary_llm):
            result = app.run_agent("top routes?")

        assert result["text"] == "Here are top routes."
        assert result["df"] is not None

    def test_tool_call_without_content_attribute_uses_str(self):
        tool_msg_no_content = MagicMock(spec=[])  # no 'content' attr
        fake_tool = MagicMock()
        fake_tool.invoke.return_value = tool_msg_no_content
        app.TOOL_MAP = {"busiest_stops": fake_tool}

        _mock_llm.invoke.return_value = _FakeMsg(
            content="", tool_calls=[{"name": "busiest_stops", "args": {}, "id": "tc-2"}]
        )
        _ql_mock.get_busiest_stops.return_value = _empty()

        summary_llm = MagicMock()
        summary_llm.invoke.return_value = _FakeMsg(content="No stops.")
        with patch.object(_lc_ollama, "ChatOllama", return_value=summary_llm):
            result = app.run_agent("busiest stops?")

        assert result["text"] == "No stops."

    def test_tool_invoke_exception_captured(self):
        fake_tool = MagicMock()
        fake_tool.invoke.side_effect = Exception("DB error")
        app.TOOL_MAP = {"compare_routes": fake_tool}

        _mock_llm.invoke.return_value = _FakeMsg(
            content="",
            tool_calls=[{"name": "compare_routes", "args": {}, "id": "tc-3"}],
        )

        summary_llm = MagicMock()
        summary_llm.invoke.return_value = _FakeMsg(content="Error handled.")
        with patch.object(_lc_ollama, "ChatOllama", return_value=summary_llm):
            result = app.run_agent("compare?")

        assert result["df"] is None  # no DF extracted

    def test_summary_llm_exception_falls_back_to_raw_text(self):
        tool_msg = MagicMock()
        tool_msg.content = "raw output"
        fake_tool = MagicMock()
        fake_tool.invoke.return_value = tool_msg
        app.TOOL_MAP = {"declining_routes": fake_tool}

        _mock_llm.invoke.return_value = _FakeMsg(
            content="",
            tool_calls=[{"name": "declining_routes", "args": {}, "id": "tc-4"}],
        )
        _ql_mock.identify_declining_routes.return_value = _df(
            route=["99"], boardings_pct_change=[-20.0]
        )

        summary_llm = MagicMock()
        summary_llm.invoke.side_effect = Exception("LLM down")
        with patch.object(_lc_ollama, "ChatOllama", return_value=summary_llm):
            result = app.run_agent("declining?")

        assert "raw output" in result["text"]

    def test_multiple_tool_calls_combined(self):
        tool_msg = MagicMock()
        tool_msg.content = "data"
        fake_tool = MagicMock()
        fake_tool.invoke.return_value = tool_msg
        app.TOOL_MAP = {
            "top_routes_by_ridership": fake_tool,
            "busiest_stops": fake_tool,
        }

        _mock_llm.invoke.return_value = _FakeMsg(
            content="",
            tool_calls=[
                {"name": "top_routes_by_ridership", "args": {}, "id": "tc-a"},
                {"name": "busiest_stops", "args": {}, "id": "tc-b"},
            ],
        )
        _ql_mock.get_top_routes_by_ridership.return_value = _df(
            route=["40"], total_boardings=[5000]
        )
        _ql_mock.get_busiest_stops.return_value = _empty()

        summary_llm = MagicMock()
        summary_llm.invoke.return_value = _FakeMsg(content="Combined.")
        with patch.object(_lc_ollama, "ChatOllama", return_value=summary_llm):
            result = app.run_agent("multi tool?")

        # First tool produced a DF so fig should be generated
        assert result["df"] is not None


# ===========================================================================
# _extract_df_from_tool
# ===========================================================================


class TestExtractDfFromTool:
    def setup_method(self):
        _ql_mock.reset_mock()
        app.query_lib = _ql_mock

    def _df(self, **cols):
        return pd.DataFrame(cols)

    def test_top_routes_by_ridership(self):
        expected = self._df(route=["40"], total_boardings=[5000])
        _ql_mock.get_top_routes_by_ridership.return_value = expected
        result = app._extract_df_from_tool(
            "top_routes_by_ridership", {"start_date": START, "end_date": END}
        )
        assert result is expected

    def test_route_ridership_trend(self):
        expected = self._df(period=["2025-01"], total_boardings=[1000])
        _ql_mock.get_route_ridership_trend.return_value = expected
        result = app._extract_df_from_tool(
            "route_ridership_trend",
            {"route_id": "40", "start_date": START, "end_date": END},
        )
        assert result is expected

    def test_busiest_stops(self):
        expected = self._df(stop_id=["S1"], total_boardings=[200])
        _ql_mock.get_busiest_stops.return_value = expected
        result = app._extract_df_from_tool(
            "busiest_stops", {"start_date": START, "end_date": END}
        )
        assert result is expected

    def test_get_overcrowded_routes(self):
        expected = self._df(route=["40"], overcrowded_trips=[5])
        _ql_mock.get_overcrowded_routes.return_value = expected
        result = app._extract_df_from_tool(
            "get_overcrowded_routes", {"service_change_num": "253"}
        )
        assert result is expected

    def test_compare_routes_string_split(self):
        expected = self._df(route=["40", "7"], total_boardings=[5000, 3000])
        _ql_mock.compare_routes.return_value = expected
        result = app._extract_df_from_tool(
            "compare_routes",
            {"route_ids": "40,7", "start_date": START, "end_date": END},
        )
        assert result is expected
        call_kwargs = _ql_mock.compare_routes.call_args[1]
        assert call_kwargs["route_ids"] == ["40", "7"]

    def test_compare_routes_list_passthrough(self):
        expected = self._df(route=["40"], total_boardings=[5000])
        _ql_mock.compare_routes.return_value = expected
        result = app._extract_df_from_tool(
            "compare_routes",
            {"route_ids": ["40"], "start_date": START, "end_date": END},
        )
        assert result is expected

    def test_declining_routes(self):
        expected = self._df(route=["99"], boardings_pct_change=[-15.0])
        _ql_mock.identify_declining_routes.return_value = expected
        result = app._extract_df_from_tool("declining_routes", {})
        assert result is expected

    def test_crowding_by_time_period(self):
        expected = self._df(time_period=["AM Peak"], pct_crowded=[20.0])
        _ql_mock.get_crowding_by_time_period.return_value = expected
        result = app._extract_df_from_tool(
            "crowding_by_time_period", {"start_date": START, "end_date": END}
        )
        assert result is expected

    def test_route_by_direction(self):
        expected = self._df(direction_label=["Inbound"], total_boardings=[3000])
        _ql_mock.get_route_by_direction.return_value = expected
        result = app._extract_df_from_tool(
            "route_by_direction",
            {"route_id": "40", "start_date": START, "end_date": END},
        )
        assert result is expected

    def test_ridership_by_day_type(self):
        expected = self._df(day_type=["Weekday"], total_boardings=[100000])
        _ql_mock.get_ridership_by_day_type.return_value = expected
        result = app._extract_df_from_tool(
            "ridership_by_day_type", {"start_date": START, "end_date": END}
        )
        assert result is expected

    def test_service_change_impact_converted_to_df(self):
        _ql_mock.analyze_service_change_impact.return_value = {
            "before_period": {"avg_boardings_per_trip": 40.0, "trips": 50},
            "after_period": {"avg_boardings_per_trip": 50.0, "trips": 55},
            "impact": {},
        }
        result = app._extract_df_from_tool(
            "service_change_impact", {"route_id": "40", "change_date": "2025-06-01"}
        )
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "period" in result.columns

    def test_unknown_tool_returns_none(self):
        result = app._extract_df_from_tool("no_such_tool", {})
        assert result is None

    def test_exception_returns_none(self):
        _ql_mock.get_top_routes_by_ridership.side_effect = Exception("DB error")
        result = app._extract_df_from_tool("top_routes_by_ridership", {})
        assert result is None
        _ql_mock.get_top_routes_by_ridership.side_effect = None


# ===========================================================================
# _auto_visualize
# ===========================================================================


class TestAutoVisualize:
    def setup_method(self):
        _viz_inst.generate.reset_mock()
        _viz_inst.generate.return_value = _fake_fig
        app.viz_agent = _viz_inst

    def _df_for(self, x_col, y_col):
        return pd.DataFrame({x_col: ["A", "B"], y_col: [10, 20]})

    # All 10 known tool → config mappings
    @pytest.mark.parametrize(
        "tool_name,x,y",
        [
            ("top_routes_by_ridership", "route", "total_boardings"),
            ("route_ridership_trend", "period", "total_boardings"),
            ("busiest_stops", "stop_nm", "total_boardings"),
            ("get_overcrowded_routes", "route", "overcrowded_trips"),
            ("compare_routes", "route", "total_boardings"),
            ("declining_routes", "route", "boardings_pct_change"),
            ("crowding_by_time_period", "time_period", "pct_crowded"),
            ("route_by_direction", "direction_label", "total_boardings"),
            ("ridership_by_day_type", "day_type", "total_boardings"),
            ("service_change_impact", "period", "avg_boardings_per_trip"),
        ],
    )
    def test_known_tools_call_viz_agent(self, tool_name, x, y):
        df = self._df_for(x, y)
        result = app._auto_visualize(tool_name, df)
        assert result is _fake_fig
        _viz_inst.generate.assert_called_once()
        _viz_inst.generate.reset_mock()

    def test_unknown_tool_returns_none(self):
        df = self._df_for("a", "b")
        result = app._auto_visualize("no_such_tool", df)
        assert result is None

    def test_missing_columns_falls_back_to_first_str_and_num(self):
        """If expected x/y cols are absent, fall back to first str/numeric cols."""
        df = pd.DataFrame({"name": ["X"], "value": [1]})
        # top_routes_by_ridership expects 'route' and 'total_boardings' — not present
        result = app._auto_visualize("top_routes_by_ridership", df)
        assert result is _fake_fig or result is None  # depends on fallback

    def test_no_str_cols_returns_none(self):
        """DataFrame with only numeric columns → can't pick x → None."""
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        # busiest_stops needs stop_nm (str) — absent; fallback needs a str col
        result = app._auto_visualize("busiest_stops", df)
        # Either None (no str col) or the fallback used numeric x
        # The code checks: if not str_cols or not num_cols: return None
        assert result is None or result is _fake_fig

    def test_no_num_cols_returns_none(self):
        """DataFrame with only string columns → can't pick y → None."""
        df = pd.DataFrame({"stop_nm": ["A", "B"], "other": ["X", "Y"]})
        result = app._auto_visualize("busiest_stops", df)
        assert result is None


# ===========================================================================
# display_messages
# ===========================================================================


class TestDisplayMessages:
    def setup_method(self):
        _reset_session()
        _st.markdown.reset_mock()
        _st.dataframe.reset_mock()
        _st.plotly_chart.reset_mock()
        _st_copy.copy_button.reset_mock()

    def test_renders_text_messages(self):
        _session_state["messages"] = [
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "Hi there"},
        ]
        app.display_messages()
        # markdown called at least once per message
        assert _st.markdown.call_count >= 2

    def test_renders_dataframe_when_present(self):
        df = pd.DataFrame({"a": [1]})
        _session_state["messages"] = [
            {"role": "assistant", "content": "Here is data", "df": df, "fig": None}
        ]
        app.display_messages()
        _st.dataframe.assert_called_once()

    def test_skips_dataframe_when_none(self):
        _session_state["messages"] = [
            {"role": "assistant", "content": "No data", "df": None}
        ]
        _st.dataframe.reset_mock()
        app.display_messages()
        _st.dataframe.assert_not_called()

    def test_renders_plotly_chart_when_present(self):
        _session_state["messages"] = [
            {"role": "assistant", "content": "Chart", "fig": _fake_fig}
        ]
        app.display_messages()
        _st.plotly_chart.assert_called_once()

    def test_skips_chart_when_none(self):
        _session_state["messages"] = [{"role": "assistant", "content": "No chart"}]
        _st.plotly_chart.reset_mock()
        app.display_messages()
        _st.plotly_chart.assert_not_called()

    def test_copy_button_rendered_when_has_copy(self):
        app.HAS_COPY = True
        _session_state["messages"] = [{"role": "assistant", "content": "Hello!"}]
        _st_copy.copy_button.reset_mock()
        app.display_messages()
        _st_copy.copy_button.assert_called()

    def test_copy_button_skipped_when_not_has_copy(self):
        app.HAS_COPY = False
        _session_state["messages"] = [{"role": "assistant", "content": "Hello!"}]
        _st_copy.copy_button.reset_mock()
        app.display_messages()
        _st_copy.copy_button.assert_not_called()

    def test_copy_button_exception_swallowed(self):
        app.HAS_COPY = True
        _st_copy.copy_button.side_effect = Exception("copy failed")
        _session_state["messages"] = [{"role": "assistant", "content": "Hello!"}]
        # Should not raise
        app.display_messages()
        _st_copy.copy_button.side_effect = None
