import pandas as pd
import requests
from agents.intent_agent import IntentAgent
from agents.analysis_agent import AnalysisAgent
from agents.prediction_agent import PredictionAgent
from agents.visualization_agent_old import VisualizationAgent
from agents.reward_system import RewardSystem
from agents.database import DatabaseManager

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"  # change to your installed model


def call_ollama(prompt: str, system: str = "") -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=60)
        return r.json().get("response", "")
    except Exception as e:
        return f"LLM error: {e}"


class TransitOrchestrator:
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()

        self.intent_agent = IntentAgent(call_ollama)
        self.analysis_agent = AnalysisAgent(self.db)
        self.prediction_agent = PredictionAgent(self.db)
        self.viz_agent = VisualizationAgent()
        self.reward = RewardSystem()

    def get_data_stats(self):
        with self.db.get_connection() as conn:
            stats = {}

            trip_count = pd.read_sql("SELECT COUNT(*) as n FROM trips;", conn).iloc[0][
                "n"
            ]
            stats["Trip Records"] = f"{int(trip_count):,}"

            stop_count = pd.read_sql(
                "SELECT COUNT(*) as n FROM stop_daily;", conn
            ).iloc[0]["n"]
            stats["Stop Records"] = f"{int(stop_count):,}"

            gis_count = pd.read_sql(
                "SELECT COUNT(DISTINCT stop_id) as n FROM stops_reference;", conn
            ).iloc[0]["n"]
            stats["GIS Stops"] = f"{int(gis_count):,}"

            date_range = pd.read_sql(
                "SELECT MIN(operation_date) as min_d, MAX(operation_date) as max_d FROM trips;",
                conn,
            ).iloc[0]
            stats["Date Range"] = f"{date_range['min_d']} → {date_range['max_d']}"

            routes = pd.read_sql(
                "SELECT COUNT(DISTINCT service_rte_num) as n FROM trips;", conn
            ).iloc[0]["n"]
            stats["Routes"] = str(int(routes))

        return stats

    def run(self, query: str) -> dict:
        agent_trace = []

        # Step 1: Intent classification by LLM
        intent = self.intent_agent.classify(query)
        agent_trace.append(
            {
                "agent": "IntentAgent",
                "action": f"Classified as: {intent['type']} | entities: {intent['entities']}",
                "reward": self.reward.score("intent", intent),
            }
        )

        # Step 2: Route to correct analysis/prediction agent (data-grounded)
        if intent["type"] == "prediction":
            analysis_result = self.prediction_agent.run(intent)
            agent_trace.append(
                {
                    "agent": "PredictionAgent",
                    "action": f"Ran: {intent.get('sub_type', 'forecast')}",
                    "reward": self.reward.score("analysis", analysis_result),
                }
            )
        else:
            analysis_result = self.analysis_agent.run(intent)
            agent_trace.append(
                {
                    "agent": "AnalysisAgent",
                    "action": f"Ran: {intent.get('sub_type', 'query')}",
                    "reward": self.reward.score("analysis", analysis_result),
                }
            )

        # Step 3: Visualization
        chart = None
        if (
            analysis_result.get("data") is not None
            and not analysis_result["data"].empty
        ):
            chart = self.viz_agent.generate(analysis_result)
            agent_trace.append(
                {
                    "agent": "VizAgent",
                    "action": f"Chart type: {analysis_result.get('chart_type', 'bar')}",
                    "reward": self.reward.score("viz", {"chart": chart}),
                }
            )

        # Step 4: LLM summarizes ONLY the analysis result (not free knowledge)
        data_summary = analysis_result.get("summary", "No data summary available.")
        system_prompt = (
            "You are a transit data analyst. Your job is ONLY to explain the provided data summary "
            "in plain English for a transit planner. Do NOT use your training knowledge. "
            "Do NOT add recommendations not supported by the data. Be concise."
        )
        llm_response = call_ollama(
            prompt=f"User asked: {query}\n\nData analysis result:\n{data_summary}\n\nExplain this clearly.",
            system=system_prompt,
        )

        agent_trace.append(
            {
                "agent": "LLM Summarizer",
                "action": "Generated natural language response from data",
                "reward": self.reward.score("response", {"response": llm_response}),
            }
        )

        return {
            "response": llm_response,
            "chart": chart,
            "table": analysis_result.get("table"),
            "agent_trace": agent_trace,
        }
