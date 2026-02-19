import pandas as pd


class RewardSystem:
    """
    Simple heuristic reward scoring for each agent step.
    Rewards are normalized to [0, 1].
    Used in the sidebar trace to show agent confidence/quality.
    """

    def score(self, agent_type: str, result: dict) -> float:
        if agent_type == "intent":
            return self._score_intent(result)
        elif agent_type == "analysis":
            return self._score_analysis(result)
        elif agent_type == "viz":
            return 1.0 if result.get("chart") is not None else 0.3
        elif agent_type == "response":
            return self._score_response(result)
        return 0.5

    def _score_intent(self, intent: dict) -> float:
        score = 0.5
        if intent.get("type") not in (None, ""):
            score += 0.25
        if intent.get("entities"):
            score += 0.25
        return min(score, 1.0)

    def _score_analysis(self, result: dict) -> float:
        score = 0.3
        data = result.get("data")
        if data is not None and isinstance(data, pd.DataFrame):
            if not data.empty:
                score += 0.4
            if len(data) > 3:
                score += 0.2
        if result.get("summary") and len(result["summary"]) > 50:
            score += 0.1
        return min(score, 1.0)

    def _score_response(self, result: dict) -> float:
        resp = result.get("response", "")
        if not resp or "error" in resp.lower():
            return 0.2
        if len(resp) > 100:
            return 0.9
        return 0.6