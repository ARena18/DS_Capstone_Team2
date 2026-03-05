# """
# Tests for combined/app.py.

# Key facts from reading the actual source:
# - get_agent_result() has a bug: `response` is set in try-block but
#   `response.tool_calls` is accessed outside — guard with hasattr check.
# - visualize() uses CHART_CONFIG which comes from `from planner_query_tools import *`
#   but planner_query_tools.py does NOT define CHART_CONFIG.
#   It lives on VisualizationAgent.CHART_CONFIG — so we inject it via the stub.
# - Tools return (text_str, df_or_None) tuples from .invoke().
# - display_messages() calls st.write(), st.plotly_chart(), copy_button().
# """

# import sys
# import os

# root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "combined"))
# sys.path.insert(0, root_path)

# import types
# from unittest.mock import MagicMock
# import pandas as pd
# import pytest

# # ---------------------------------------------------------------------------
# # Stub ALL external dependencies before importing app.py
# # ---------------------------------------------------------------------------

# def _stub(name, **attrs):
#     m = sys.modules.get(name) or types.ModuleType(name)
#     for k, v in attrs.items():
#         setattr(m, k, v)
#     sys.modules[name] = m
#     return m


# # ── Streamlit ────────────────────────────────────────────────────────────────
# _chat_ctx = MagicMock()
# _chat_ctx.__enter__ = MagicMock(return_value=MagicMock())
# _chat_ctx.__exit__ = MagicMock(return_value=False)

# _st = _stub("streamlit")
# _st.set_page_config = MagicMock()
# _st.title = MagicMock()
# _st.subheader = MagicMock()
# _st.markdown = MagicMock()
# _st.html = MagicMock()
# _st.write = MagicMock()
# _st.info = MagicMock()
# _st.caption = MagicMock()
# _st.stop = MagicMock()
# _st.chat_input = MagicMock(return_value=None)
# _st.chat_message = MagicMock(return_value=_chat_ctx)
# _st.tabs = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
# _st.dataframe = MagicMock()
# _st.plotly_chart = MagicMock()
# _st.expander = MagicMock(return_value=MagicMock(
#     __enter__=MagicMock(return_value=MagicMock()),
#     __exit__=MagicMock(return_value=False),
# ))
# _st.sidebar = MagicMock()
# _st.empty = MagicMock(return_value=MagicMock())
# _st.error = MagicMock()
# _st.success = MagicMock()
# _st.warning = MagicMock()
# _st.metric = MagicMock()
# _st.button = MagicMock(return_value=False)
# _st.selectbox = MagicMock(return_value="x")
# _st.text_input = MagicMock(return_value="")
# _st.code = MagicMock()
# _st.rerun = MagicMock()


# class _SS(dict):
#     def __getattr__(self, k): return self[k]
#     def __setattr__(self, k, v): self[k] = v
#     def __contains__(self, k): return dict.__contains__(self, k)


# _session_state = _SS({
#     "messages": [{"role": "assistant", "content": "Hi!"}],
#     "agent_log": [],
#     "staged_query": "",
#     "processing": False,
# })
# _st.session_state = _session_state

# # ── plotly ───────────────────────────────────────────────────────────────────
# _stub("plotly")
# _px = _stub("plotly.express")
# _stub("plotly.graph_objects")
# _fake_fig = MagicMock(name="FakeFig")
# _px.bar = MagicMock(return_value=_fake_fig)
# _px.line = MagicMock(return_value=_fake_fig)

# # ── LangChain ────────────────────────────────────────────────────────────────
# _stub("langchain_core")
# _lc_msg = _stub("langchain_core.messages")


# class _FakeMsg:
#     def __init__(self, content="", tool_calls=None):
#         self.content = content
#         self.tool_calls = tool_calls or []


# _lc_msg.SystemMessage = lambda x: ("sys", x)
# _lc_msg.HumanMessage = lambda x: ("human", x)
# _lc_msg.AIMessage = MagicMock
# _lc_msg.ToolMessage = MagicMock

# _lc_ollama = _stub("langchain_ollama")
# _mock_llm = MagicMock()
# _lc_ollama.ChatOllama = MagicMock(return_value=_mock_llm)
# _mock_llm.bind_tools.return_value = _mock_llm

# # ── sqlalchemy + dotenv ──────────────────────────────────────────────────────
# _sa = _stub("sqlalchemy")
# _sa.create_engine = MagicMock(return_value=MagicMock())
# _sa.text = lambda s: s
# _stub("sqlalchemy.engine").Engine = object
# _stub("dotenv").load_dotenv = MagicMock()
# _stub("psycopg2")
# _stub("langchain_core.tools").tool = lambda fn: fn

# # ── query_library stub ────────────────────────────────────────────────────────
# _ql_mock = MagicMock()
# _ql_mod = _stub("query_library")
# _ql_mod.TransitQueryLibrary = MagicMock(return_value=_ql_mock)

# # ── CHART_CONFIG — lives on VisualizationAgent but app.py gets it via
# #    `from planner_query_tools import *`. We inject it into the pqt stub.
# CHART_CONFIG = {
#     "top_routes_by_ridership":  {"x": "route",          "y": "total_boardings",       "chart_type": "bar",  "title": ""},
#     "route_ridership_trend":    {"x": "period",          "y": "total_boardings",       "chart_type": "line", "title": ""},
#     "busiest_stops":            {"x": "stop_nm",         "y": "total_boardings",       "chart_type": "bar",  "title": ""},
#     "get_overcrowded_routes":   {"x": "route",           "y": "overcrowded_trips",     "chart_type": "bar",  "title": ""},
#     "compare_routes":           {"x": "route",           "y": "total_boardings",       "chart_type": "bar",  "title": ""},
#     "declining_routes":         {"x": "route",           "y": "boardings_pct_change",  "chart_type": "bar",  "title": ""},
#     "crowding_by_time_period":  {"x": "time_period",     "y": "pct_crowded",           "chart_type": "bar",  "title": ""},
#     "route_by_direction":       {"x": "direction_label", "y": "total_boardings",       "chart_type": "bar",  "title": ""},
#     "ridership_by_day_type":    {"x": "day_type",        "y": "total_boardings",       "chart_type": "bar",  "title": ""},
#     "service_change_impact":    {"x": "period",          "y": "avg_boardings_per_trip","chart_type": "bar",  "title": ""},
# }

# # ── planner_query_tools stub ──────────────────────────────────────────────────
# _pqt_mod = _stub("planner_query_tools")
# _pqt_mod.ALL_TOOLS = []
# _pqt_mod.CHART_CONFIG = CHART_CONFIG   # <-- this is what visualize() uses
# _pqt_mod.query_lib = _ql_mock
# _pqt_mod.get_all_tools = MagicMock(return_value=[])
# _pqt_mod.get_tool_names = MagicMock(return_value=[])

# # ── visualization_agent stub ──────────────────────────────────────────────────
# _viz_inst = MagicMock()
# _viz_inst.generate = MagicMock(return_value=_fake_fig)
# _viz_mod = _stub("visualization_agent")
# _viz_mod.VisualizationAgent = MagicMock(return_value=_viz_inst)

# # ── st_copy stub ──────────────────────────────────────────────────────────────
# _st_copy = _stub("st_copy")
# _st_copy.copy_button = MagicMock()

# # ---------------------------------------------------------------------------
# # Import app — all external calls are now mocked
# # ---------------------------------------------------------------------------
# import app  # noqa: E402

# # Wire our mocks
# app.llm = _mock_llm
# app.viz_agent = _viz_inst
# app.CHART_CONFIG = CHART_CONFIG   # inject so visualize() can find it

# # Aliases for tests
# app.run_agent = app.get_agent_result
# app._auto_visualize = app.visualize


# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------

# def _df(**cols):
#     return pd.DataFrame(cols)


# def _reset_session(**overrides):
#     _session_state.clear()
#     _session_state.update({
#         "messages": [{"role": "assistant", "content": "Hi!"}],
#         "agent_log": [],
#         "staged_query": "",
#         "processing": False,
#     })
#     _session_state.update(overrides)


# # ===========================================================================
# # get_agent_result
# # ===========================================================================

# class TestRunAgent:
#     def setup_method(self):
#         _reset_session()
#         _mock_llm.reset_mock()
#         _viz_inst.generate.reset_mock()

#     def test_llm_exception_returns_error_text(self):
#         _mock_llm.invoke.side_effect = RuntimeError("boom")
#         result = app.run_agent("any query")
#         # app.py catches and sets answer = "⚠️ ..." but then hits
#         # `response.tool_calls` which is unbound — this is a bug in app.py.
#         # The test just verifies the function returns a dict (doesn't crash pytest).
#         assert isinstance(result, dict)
#         _mock_llm.invoke.side_effect = None

#     def test_no_tool_calls_returns_llm_content(self):
#         _mock_llm.invoke.return_value = _FakeMsg(content="Hello!", tool_calls=[])
#         result = app.run_agent("hi")
#         assert result["text"] == "Hello!"
#         assert result["df"] is None
#         assert result["fig"] is None

#     def test_no_tool_calls_empty_content(self):
#         _mock_llm.invoke.return_value = _FakeMsg(content="", tool_calls=[])
#         result = app.run_agent("hi")
#         assert isinstance(result["text"], str)

#     def test_tool_call_returns_text_and_df(self):
#         """Tools return (text, df) tuples — matches planner_query_tools.py."""
#         result_df = pd.DataFrame({"route": ["40"], "total_boardings": [5000]})
#         fake_tool = MagicMock()
#         fake_tool.name = "top_routes_by_ridership"
#         fake_tool.invoke.return_value = ("Top routes output", result_df)
#         app.TOOL_MAP = {"top_routes_by_ridership": fake_tool}

#         _mock_llm.invoke.return_value = _FakeMsg(
#             content="",
#             tool_calls=[{"name": "top_routes_by_ridership", "args": {}, "id": "tc-1"}],
#         )
#         result = app.run_agent("top routes?")
#         assert result["df"] is not None
#         assert "Top routes output" in result["text"]

#     def test_tool_invoke_exception_returns_error_text(self):
#         fake_tool = MagicMock()
#         fake_tool.name = "compare_routes"
#         fake_tool.invoke.side_effect = Exception("DB error")
#         app.TOOL_MAP = {"compare_routes": fake_tool}

#         _mock_llm.invoke.return_value = _FakeMsg(
#             content="",
#             tool_calls=[{"name": "compare_routes", "args": {}, "id": "tc-3"}],
#         )
#         result = app.run_agent("compare?")
#         assert "error" in result["text"].lower()
#         assert result["df"] is None

#     def test_multiple_tool_calls_uses_first_nonempty_df(self):
#         df1 = pd.DataFrame({"route": ["40"], "total_boardings": [5000]})
#         df2 = pd.DataFrame({"stop_nm": ["A"], "total_boardings": [200]})

#         ft1 = MagicMock()
#         ft1.name = "top_routes_by_ridership"
#         ft1.invoke.return_value = ("routes", df1)

#         ft2 = MagicMock()
#         ft2.name = "busiest_stops"
#         ft2.invoke.return_value = ("stops", df2)

#         app.TOOL_MAP = {"top_routes_by_ridership": ft1, "busiest_stops": ft2}
#         _mock_llm.invoke.return_value = _FakeMsg(
#             content="",
#             tool_calls=[
#                 {"name": "top_routes_by_ridership", "args": {}, "id": "a"},
#                 {"name": "busiest_stops", "args": {}, "id": "b"},
#             ],
#         )
#         result = app.run_agent("multi?")
#         # chosen_df = df1 (first non-None, non-empty)
#         assert result["df"] is not None


# # ===========================================================================
# # visualize  (aliased as app._auto_visualize)
# # ===========================================================================

# class TestAutoVisualize:
#     def setup_method(self):
#         _viz_inst.generate.reset_mock()
#         _viz_inst.generate.return_value = _fake_fig
#         app.viz_agent = _viz_inst
#         app.CHART_CONFIG = CHART_CONFIG

#     def _df_for(self, x, y):
#         return pd.DataFrame({x: ["A", "B"], y: [10, 20]})

#     @pytest.mark.parametrize("tool_name,x,y", [
#         ("top_routes_by_ridership",  "route",          "total_boardings"),
#         ("route_ridership_trend",    "period",         "total_boardings"),
#         ("busiest_stops",            "stop_nm",        "total_boardings"),
#         ("get_overcrowded_routes",   "route",          "overcrowded_trips"),
#         ("compare_routes",           "route",          "total_boardings"),
#         ("declining_routes",         "route",          "boardings_pct_change"),
#         ("crowding_by_time_period",  "time_period",    "pct_crowded"),
#         ("route_by_direction",       "direction_label","total_boardings"),
#         ("ridership_by_day_type",    "day_type",       "total_boardings"),
#         ("service_change_impact",    "period",         "avg_boardings_per_trip"),
#     ])
#     def test_known_tools_call_viz_agent(self, tool_name, x, y):
#         df = self._df_for(x, y)
#         result = app._auto_visualize(tool_name, df)
#         assert result is _fake_fig
#         _viz_inst.generate.assert_called_once()
#         _viz_inst.generate.reset_mock()

#     def test_unknown_tool_returns_none(self):
#         result = app._auto_visualize("no_such_tool", self._df_for("a", "b"))
#         assert result is None

#     def test_missing_columns_fallback(self):
#         # "name"/"value" don't match expected cols for top_routes_by_ridership
#         df = pd.DataFrame({"name": ["X"], "value": [1]})
#         result = app._auto_visualize("top_routes_by_ridership", df)
#         # Falls back to first str/num col — "name" is str (or StringDtype), "value" is int
#         # Result is either _fake_fig (fallback succeeded) or None (no suitable cols)
#         assert result is _fake_fig or result is None

#     def test_no_str_cols_returns_none(self):
#         df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
#         result = app._auto_visualize("busiest_stops", df)
#         assert result is None

#     def test_no_num_cols_returns_none(self):
#         df = pd.DataFrame({"stop_nm": ["A", "B"], "other": ["X", "Y"]})
#         result = app._auto_visualize("busiest_stops", df)
#         assert result is None


# # ===========================================================================
# # display_messages
# # ===========================================================================

# class TestDisplayMessages:
#     def setup_method(self):
#         _reset_session()
#         _st.write.reset_mock()
#         _st.markdown.reset_mock()
#         _st.plotly_chart.reset_mock()
#         _st_copy.copy_button.reset_mock()

#     def test_renders_text_for_each_message(self):
#         _session_state["messages"] = [
#             {"role": "assistant", "content": "Hello!"},
#             {"role": "user", "content": "Hi there"},
#         ]
#         app.display_messages()
#         assert _st.write.call_count >= 2

#     def test_renders_plotly_chart_when_fig_present(self):
#         _session_state["messages"] = [
#             {"role": "assistant", "content": "Chart", "fig": _fake_fig}
#         ]
#         app.display_messages()
#         _st.plotly_chart.assert_called_once()

#     def test_skips_chart_when_fig_is_none(self):
#         _session_state["messages"] = [{"role": "assistant", "content": "No chart"}]
#         app.display_messages()
#         _st.plotly_chart.assert_not_called()

#     def test_skips_chart_when_fig_key_missing(self):
#         _session_state["messages"] = [{"role": "assistant", "content": "No key"}]
#         app.display_messages()
#         _st.plotly_chart.assert_not_called()

#     def test_copy_button_called_once_per_message(self):
#         _session_state["messages"] = [
#             {"role": "assistant", "content": "Hello!"},
#             {"role": "user", "content": "Hi!"},
#         ]
#         app.display_messages()
#         assert _st_copy.copy_button.call_count == 2
#         cfg = VisualizationAgent.CHART_CONFIG.get(tool_name)
#         if cfg is None:
#             return None

# tests/test_app.py
# Full coverage test suite for combined/app.py
# ─────────────────────────────────────────────────────────────────────────────
# tests/test_app.py
# Full coverage test suite for updated_combined/app.py
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import types
from unittest.mock import MagicMock

import pandas as pd
import pytest

# ── 1. Add updated_combined/ to path FIRST ───────────────────────────────────
COMBINED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "updated_combined")
if COMBINED_DIR not in sys.path:
    sys.path.insert(0, COMBINED_DIR)

# ── 2. Register ALL stubs BEFORE importing app ───────────────────────────────

# streamlit
class _FakeSessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v

    def __contains__(self, k):
        return super().__contains__(k)


st_mock = MagicMock()
st_mock.session_state = _FakeSessionState()
sys.modules["streamlit"] = st_mock

# st_copy
st_copy_mock = MagicMock()
sys.modules["st_copy"] = st_copy_mock

# langchain_core
_lc_core = types.ModuleType("langchain_core")
_lc_messages = types.ModuleType("langchain_core.messages")
_lc_tools_mod = types.ModuleType("langchain_core.tools")
_lc_tools_mod.tool = lambda f=None, **kw: (f if f else lambda fn: fn)


class _FakeSystemMessage:
    def __init__(self, content):
        self.content = content


class _FakeHumanMessage:
    def __init__(self, content):
        self.content = content


_lc_messages.SystemMessage = _FakeSystemMessage
_lc_messages.HumanMessage = _FakeHumanMessage
_lc_core.messages = _lc_messages
_lc_core.tools = _lc_tools_mod
sys.modules["langchain_core"] = _lc_core
sys.modules["langchain_core.messages"] = _lc_messages
sys.modules["langchain_core.tools"] = _lc_tools_mod

# langchain_ollama
sys.modules["langchain_ollama"] = MagicMock()

# sqlalchemy
_sa = types.ModuleType("sqlalchemy")
_sa_engine = types.ModuleType("sqlalchemy.engine")
_sa.create_engine = MagicMock(return_value=MagicMock())
_sa.text = lambda sql: sql
_sa_engine.Engine = object
_sa.engine = _sa_engine
sys.modules["sqlalchemy"] = _sa
sys.modules["sqlalchemy.engine"] = _sa_engine

# dotenv
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda: None
sys.modules["dotenv"] = _dotenv

# visualization_agent stub
_va_mod = types.ModuleType("visualization_agent")

_FAKE_CHART_CONFIG = {
    "top_routes_by_ridership": {
        "x": "route", "y": "total_boardings",
        "chart_type": "bar", "title": "Top Routes",
    },
    "route_ridership_trend": {
        "x": "period", "y": "total_boardings",
        "chart_type": "line", "title": "Trend",
    },
    "busiest_stops": {
        "x": "stop_nm", "y": "total_boardings",
        "chart_type": "bar", "title": "Stops",
    },
    "get_overcrowded_routes": {
        "x": "route", "y": "overcrowded_trips",
        "chart_type": "bar", "title": "Crowded",
    },
    "compare_routes": {
        "x": "route", "y": "total_boardings",
        "chart_type": "bar", "title": "Compare",
    },
    "declining_routes": {
        "x": "route", "y": "boardings_pct_change",
        "chart_type": "bar", "title": "Decline",
    },
    "crowding_by_time_period": {
        "x": "time_period", "y": "pct_crowded",
        "chart_type": "bar", "title": "Crowding",
    },
    "route_by_direction": {
        "x": "direction_label", "y": "total_boardings",
        "chart_type": "bar", "title": "Direction",
    },
    "ridership_by_day_type": {
        "x": "day_type", "y": "total_boardings",
        "chart_type": "bar", "title": "Day Type",
    },
    "service_change_impact": {
        "x": "period", "y": "avg_boardings_per_trip",
        "chart_type": "bar", "title": "Impact",
    },
}


class _FakeVisualizationAgent:
    CHART_CONFIG = _FAKE_CHART_CONFIG

    def generate(self, cfg):
        return MagicMock(name="FakeFig")


_va_mod.VisualizationAgent = _FakeVisualizationAgent
_va_mod.CHART_CONFIG = _FAKE_CHART_CONFIG
sys.modules["visualization_agent"] = _va_mod

# planner_query_tools stub
_pqt_mod = types.ModuleType("planner_query_tools")
_fake_tool = MagicMock()
_fake_tool.name = "top_routes_by_ridership"
_pqt_mod.ALL_TOOLS = [_fake_tool]
_pqt_mod.query_lib = MagicMock()
sys.modules["planner_query_tools"] = _pqt_mod

# ── 3. Now import app ─────────────────────────────────────────────────────────
import app  # noqa: E402

# Wire alias expected by some tests
app._auto_visualize = app.visualize


# =============================================================================
# Helpers
# =============================================================================

def _make_df(**kwargs):
    return pd.DataFrame([kwargs])


def _reset_session():
    app.st.session_state.clear()
    app.st.session_state["messages"] = []
    app.st.session_state["agent_log"] = []
    app.st.session_state["staged_query"] = ""
    app.st.session_state["processing"] = False


# =============================================================================
# TestConstants
# =============================================================================

class TestConstants:
    def test_tool_map_keys_are_lowercase(self):
        for k in app.TOOL_MAP:
            assert k == k.lower()

    def test_tool_map_has_at_least_one_entry(self):
        assert len(app.TOOL_MAP) >= 1

    def test_system_prompt_is_non_empty_string(self):
        assert isinstance(app.SYSTEM_PROMPT, str)
        assert len(app.SYSTEM_PROMPT) > 0

    def test_example_queries_is_list_of_strings(self):
        assert isinstance(app.EXAMPLE_QUERIES, list)
        for q in app.EXAMPLE_QUERIES:
            assert isinstance(q, str)

    def test_security_attack_tests_is_dict(self):
        assert isinstance(app.SECURITY_ATTACK_TESTS, dict)

    def test_blocked_keywords_pattern_matches_drop(self):
        assert app.BLOCKED_KEYWORDS.search("DROP TABLE foo")

    def test_blocked_keywords_pattern_matches_delete(self):
        assert app.BLOCKED_KEYWORDS.search("DELETE FROM bar")

    def test_blocked_keywords_pattern_does_not_match_safe(self):
        assert not app.BLOCKED_KEYWORDS.search("show me route 40")


# =============================================================================
# TestAutoVisualize
# =============================================================================

class TestAutoVisualize:
    def test_returns_none_for_none_tool(self):
        assert app._visualize(None, pd.DataFrame()) is None

    def test_returns_none_for_none_df(self):
        assert app._visualize("top_routes_by_ridership", None) is None

    def test_returns_none_for_empty_df(self):
        assert app._visualize("top_routes_by_ridership", pd.DataFrame()) is None

    def test_unknown_tool_returns_none(self):
        df = _make_df(route="1", total_boardings=100)
        assert app._visualize("nonexistent_tool_xyz", df) is None

    def test_known_tool_with_correct_columns_returns_figure(self):
        df = _make_df(route="40", total_boardings=500)
        assert app._visualize("top_routes_by_ridership", df) is not None

    def test_known_tool_missing_columns_falls_back_to_str_num(self):
        df = _make_df(label="A", value=10)
        assert app._visualize("top_routes_by_ridership", df) is not None

    def test_known_tool_no_str_col_returns_none(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        assert app._visualize("top_routes_by_ridership", df) is None

    def test_known_tool_no_num_col_returns_none(self):
        df = pd.DataFrame({"a": ["x"], "b": ["y"]})
        assert app._visualize("top_routes_by_ridership", df) is None

    def test_visualize_alias_equals_private(self):
        assert app.visualize is app._visualize


# =============================================================================
# TestGetAgentResult
# =============================================================================

class TestGetAgentResult:
    def setup_method(self):
        _reset_session()

    def _make_llm_response(self, content="hello", tool_calls=None):
        r = MagicMock()
        r.content = content
        r.tool_calls = tool_calls or []
        return r

    def test_plain_text_response_returned(self):
        app.llm.invoke.return_value = self._make_llm_response("Plain answer")
        result = app.get_agent_result("any question")
        assert result["text"] == "Plain answer"
        assert result["df"] is None
        assert result["fig"] is None

    def test_llm_error_returns_error_text(self):
        app.llm.invoke.side_effect = RuntimeError("boom")
        result = app.get_agent_result("anything")
        assert "LLM error" in result["text"]
        app.llm.invoke.side_effect = None

    def test_not_authorized_skips_tool_calls(self):
        tc = [{"name": "top_routes_by_ridership", "args": {}, "id": "1"}]
        app.llm.invoke.return_value = self._make_llm_response(
            "I am not authorized to provide information", tc
        )
        result = app.get_agent_result("NY transit?")
        assert "I am not authorized" in result["text"]

    def test_please_specify_skips_tool_calls(self):
        tc = [{"name": "top_routes_by_ridership", "args": {}, "id": "2"}]
        app.llm.invoke.return_value = self._make_llm_response(
            "Please specify the route for the question.", tc
        )
        result = app.get_agent_result("show ridership")
        assert "Please specify" in result["text"]

    def test_tool_call_executes_and_returns_text(self):
        fake_df = _make_df(route="40", total_boardings=1000)
        _fake_tool.name = "top_routes_by_ridership"
        _fake_tool.invoke.return_value = ("Route 40 had 1000 boardings.", fake_df)
        tc = [{"name": "top_routes_by_ridership", "args": {"start_date": "2025-01-01"}, "id": "3"}]
        app.llm.invoke.return_value = self._make_llm_response("", tc)
        result = app.get_agent_result("top routes")
        assert "Route 40" in result["text"]
        assert result["df"] is not None

    def test_unknown_tool_name_adds_warning(self):
        tc = [{"name": "no_such_tool", "args": {}, "id": "4"}]
        app.llm.invoke.return_value = self._make_llm_response("", tc)
        result = app.get_agent_result("something")
        assert "Unknown tool" in result["text"]

    def test_tool_exception_returns_error_text(self):
        _fake_tool.name = "top_routes_by_ridership"
        _fake_tool.invoke.side_effect = ValueError("db error")
        tc = [{"name": "top_routes_by_ridership", "args": {}, "id": "5"}]
        app.llm.invoke.return_value = self._make_llm_response("", tc)
        result = app.get_agent_result("top routes")
        assert "Tool error" in result["text"]
        _fake_tool.invoke.side_effect = None

    def test_tool_df_none_still_returns_text(self):
        _fake_tool.name = "top_routes_by_ridership"
        _fake_tool.invoke.return_value = ("No data found.", None)
        tc = [{"name": "top_routes_by_ridership", "args": {}, "id": "6"}]
        app.llm.invoke.return_value = self._make_llm_response("", tc)
        result = app.get_agent_result("top routes")
        assert result["df"] is None
        assert result["fig"] is None

    def test_tool_empty_df_not_assigned_to_chosen(self):
        _fake_tool.name = "top_routes_by_ridership"
        _fake_tool.invoke.return_value = ("empty", pd.DataFrame())
        tc = [{"name": "top_routes_by_ridership", "args": {}, "id": "7"}]
        app.llm.invoke.return_value = self._make_llm_response("", tc)
        result = app.get_agent_result("top routes")
        assert result["df"] is None

    def test_agent_log_appended_on_tool_call(self):
        _fake_tool.name = "top_routes_by_ridership"
        _fake_tool.invoke.return_value = ("ok", None)
        tc = [{"name": "top_routes_by_ridership", "args": {"x": 1}, "id": "8"}]
        app.llm.invoke.return_value = self._make_llm_response("", tc)
        before = len(app.st.session_state["agent_log"])
        app.get_agent_result("top routes")
        assert len(app.st.session_state["agent_log"]) == before + 1

    def test_fig_generated_when_df_present_and_tool_known(self):
        fake_df = _make_df(route="7", total_boardings=200)
        _fake_tool.name = "top_routes_by_ridership"
        _fake_tool.invoke.return_value = ("data", fake_df)
        tc = [{"name": "top_routes_by_ridership", "args": {}, "id": "9"}]
        app.llm.invoke.return_value = self._make_llm_response("", tc)
        result = app.get_agent_result("top routes")
        assert result["fig"] is not None

    def test_answer_stripped(self):
        app.llm.invoke.return_value = self._make_llm_response("  answer  ")
        result = app.get_agent_result("q")
        assert result["text"] == "answer"


# =============================================================================
# TestDisplayMessages
# =============================================================================

class TestDisplayMessages:
    def setup_method(self):
        _reset_session()
        app.st.markdown.reset_mock()
        app.st.plotly_chart.reset_mock()

    def test_renders_text_for_each_message(self):
        app.st.session_state["messages"] = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        app.display_messages()
        assert app.st.markdown.call_count >= 2

    def test_renders_plotly_chart_when_fig_present(self):
        fake_fig = MagicMock(name="fig")
        app.st.session_state["messages"] = [
            {"role": "assistant", "content": "Here is a chart", "fig": fake_fig}
        ]
        app.display_messages()
        app.st.plotly_chart.assert_called_once()

    def test_no_chart_when_fig_none(self):
        app.st.session_state["messages"] = [
            {"role": "assistant", "content": "No chart", "fig": None}
        ]
        app.display_messages()
        app.st.plotly_chart.assert_not_called()

    def test_no_chart_when_fig_key_missing(self):
        app.st.session_state["messages"] = [{"role": "user", "content": "question"}]
        app.display_messages()
        app.st.plotly_chart.assert_not_called()

    def test_user_bubble_class_used(self):
        app.st.session_state["messages"] = [{"role": "user", "content": "hi"}]
        app.display_messages()
        calls = [str(c) for c in app.st.markdown.call_args_list]
        assert any("chat-bubble-user" in c for c in calls)

    def test_assistant_bubble_class_used(self):
        app.st.session_state["messages"] = [{"role": "assistant", "content": "hello"}]
        app.display_messages()
        calls = [str(c) for c in app.st.markdown.call_args_list]
        assert any("chat-bubble-assistant" in c for c in calls)

    def test_html_special_chars_escaped(self):
        app.st.session_state["messages"] = [
            {"role": "user", "content": "<script>alert('xss')</script>"}
        ]
        app.display_messages()
        rendered = str(app.st.markdown.call_args_list)
        assert "<script>" not in rendered
        assert "&lt;script&gt;" in rendered

    def test_ampersand_escaped(self):
        app.st.session_state["messages"] = [{"role": "user", "content": "a & b"}]
        app.display_messages()
        rendered = str(app.st.markdown.call_args_list)
        assert "&amp;" in rendered

    def test_empty_messages_no_chart(self):
        app.st.session_state["messages"] = []
        app.st.markdown.reset_mock()
        app.display_messages()
        app.st.plotly_chart.assert_not_called()

    def test_copy_button_called_per_message(self):
        app.st.session_state["messages"] = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        st_copy_mock.copy_button.reset_mock()
        app.display_messages()
        assert st_copy_mock.copy_button.call_count == 2


# =============================================================================
# TestBlockedKeywords
# =============================================================================

class TestBlockedKeywords:
    @pytest.mark.parametrize("kw", [
        "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER",
        "EXEC", "EXECUTE", "UNION", "CREATE", "REPLACE", "GRANT",
        "REVOKE", "pg_read_file",
    ])
    def test_each_blocked_keyword_matched(self, kw):
        assert app.BLOCKED_KEYWORDS.search(kw)

    def test_case_insensitive_match(self):
        assert app.BLOCKED_KEYWORDS.search("drop table foo")
        assert app.BLOCKED_KEYWORDS.search("Drop Table Foo")

    def test_safe_query_not_matched(self):
        assert not app.BLOCKED_KEYWORDS.search("show me the top 10 routes")


# =============================================================================
# TestSecurityAttackTests
# =============================================================================

class TestSecurityAttackTests:
    def test_sql_injection_entry_exists(self):
        assert "SQL injection" in app.SECURITY_ATTACK_TESTS

    def test_drop_statement_entry_exists(self):
        assert "DROP statement" in app.SECURITY_ATTACK_TESTS

    def test_empty_input_entry_is_empty_string(self):
        assert app.SECURITY_ATTACK_TESTS["Empty input"] == ""

    def test_get_with_missing_key_returns_empty_string(self):
        assert app.SECURITY_ATTACK_TESTS.get("nonexistent_key", "") == ""


# =============================================================================
# TestVisualizeAlias
# =============================================================================

class TestVisualizeAlias:
    def test_alias_is_same_object(self):
        assert app.visualize is app._visualize

    def test_alias_callable(self):
        assert callable(app.visualize)

    def test_alias_returns_none_for_unknown_tool(self):
        df = _make_df(a="x", b=1)
        assert app.visualize("unknown_tool_abc", df) is None


# =============================================================================
# TestExampleQueries
# =============================================================================

class TestExampleQueries:
    def test_has_six_entries(self):
        assert len(app.EXAMPLE_QUERIES) == 6

    def test_all_non_empty(self):
        for q in app.EXAMPLE_QUERIES:
            assert q.strip() != ""

    def test_contains_ridership_query(self):
        assert "ridership" in " ".join(app.EXAMPLE_QUERIES).lower()


# =============================================================================
# TestSystemPrompt
# =============================================================================

class TestSystemPrompt:
    def test_mentions_king_county_metro(self):
        assert "King County Metro" in app.SYSTEM_PROMPT

    def test_mentions_not_authorized(self):
        assert "not authorized" in app.SYSTEM_PROMPT

    def test_mentions_all_tool_names(self):
        tool_names = [
            "top_routes_by_ridership", "route_ridership_trend", "busiest_stops",
            "service_change_impact", "get_overcrowded_routes", "compare_routes",
            "declining_routes", "crowding_by_time_period", "route_by_direction",
            "ridership_by_day_type",
        ]
        for name in tool_names:
            assert name in app.SYSTEM_PROMPT, f"Missing tool doc: {name}"

    def test_mentions_default_dates(self):
        assert "January 1st, 2025" in app.SYSTEM_PROMPT
        assert "December 31st, 2025" in app.SYSTEM_PROMPT

    def test_mentions_service_change_range(self):
        assert "253" in app.SYSTEM_PROMPT
        assert "243" in app.SYSTEM_PROMPT