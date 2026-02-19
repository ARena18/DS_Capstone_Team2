import json
import re


INTENT_SYSTEM = """You are an intent classifier for transit data queries.
Classify the user query into one of these types:
- boardings_analysis: questions about passenger boardings/alightings at stops
- crowding_analysis: questions about crowding, load, threshold
- schedule_adherence: questions about delays, on-time performance
- route_comparison: comparing routes or inbound/outbound
- stop_performance: stop-level performance, underperforming stops
- geographic: zip code, fare zone, spatial queries
- prediction: forecasting, predicting future load/demand

Extract entities:
- route: route number if mentioned (e.g. 677, 1)
- stop: stop name or ID if mentioned
- day_type: WK (weekday), SAT, SUN, HOL
- time_period: AM Peak, PM Peak, Midday, etc.
- zone: fare zone number
- zip: zip code

Respond ONLY with valid JSON like:
{"type": "boardings_analysis", "sub_type": "top_stops", "entities": {"route": "677", "day_type": "WK"}}
"""


class IntentAgent:
    def __init__(self, llm_fn):
        self.llm = llm_fn

    def classify(self, query: str) -> dict:
        raw = self.llm(prompt=query, system=INTENT_SYSTEM)
        try:
            # Extract JSON from response
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        # Fallback: rule-based classification
        return self._rule_based(query)

    def _rule_based(self, query: str) -> dict:
        q = query.lower()
        entities = {}

        # Extract route number
        route_match = re.search(r'route\s*(\d+)', q)
        if route_match:
            entities["route"] = route_match.group(1)

        # Day type
        if any(w in q for w in ["weekday", "wk"]):
            entities["day_type"] = "WK"
        elif "holiday" in q or "hol" in q:
            entities["day_type"] = "HOL"

        # Time period
        for tp in ["am peak", "pm peak", "midday", "evening"]:
            if tp in q:
                entities["time_period"] = tp.title()

        # Fare zone
        zone_match = re.search(r'zone\s*(\d+)', q)
        if zone_match:
            entities["zone"] = zone_match.group(1)

        # ZIP
        zip_match = re.search(r'\b9\d{4}\b', q)
        if zip_match:
            entities["zip"] = zip_match.group()

        # Intent type
        if any(w in q for w in ["predict", "forecast", "next week", "expected"]):
            return {"type": "prediction", "sub_type": "load_forecast", "entities": entities}
        if any(w in q for w in ["crowd", "threshold", "overload", "capacity"]):
            return {"type": "crowding_analysis", "sub_type": "threshold_check", "entities": entities}
        if any(w in q for w in ["delay", "late", "on-time", "adherence", "schedule"]):
            return {"type": "schedule_adherence", "sub_type": "delay_analysis", "entities": entities}
        if any(w in q for w in ["inbound", "outbound", "compare route", "vs"]):
            return {"type": "route_comparison", "sub_type": "direction_compare", "entities": entities}
        if any(w in q for w in ["zone", "zip", "geographic", "map", "spatial"]):
            return {"type": "geographic", "sub_type": "zone_analysis", "entities": entities}
        if any(w in q for w in ["underperform", "low boarding", "low ridership"]):
            return {"type": "stop_performance", "sub_type": "underperforming", "entities": entities}

        return {"type": "boardings_analysis", "sub_type": "top_stops", "entities": entities}