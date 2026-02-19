import pandas as pd
import numpy as np


class PredictionAgent:
    def __init__(self, db_manager):
        self.db = db_manager

    def run(self, intent: dict) -> dict:
        sub = intent.get("sub_type", "load_forecast")
        e = intent.get("entities", {})

        if sub == "load_forecast":
            return self._load_forecast(e)
        return self._load_forecast(e)

    def _load_forecast(self, e: dict) -> dict:
        filters = []
        if e.get("route"):
            filters.append(f"service_rte_num = '{e['route']}'")
        if e.get("time_period"):
            filters.append(f"LOWER(time_period) = '{e['time_period'].lower()}'")
        
        where = "WHERE " + " AND ".join(filters) if filters else ""
        
        # Get daily avg load per route
        query = f"""
            SELECT 
                operation_date,
                service_rte_num,
                AVG(max_psngr_load) as avg_load,
                AVG(psngr_boardings) as avg_boardings
            FROM trips
            {where}
            GROUP BY operation_date, service_rte_num
            ORDER BY operation_date, service_rte_num;
        """
        
        with self.db.get_connection() as conn:
            daily = pd.read_sql(query, conn)
        
        # Calculate 7-day rolling average
        daily["rolling_avg_load"] = (
            daily.groupby("service_rte_num")["avg_load"]
            .transform(lambda x: x.rolling(7, min_periods=1).mean())
        )
        
        # Calculate linear trend per route
        forecasts = []
        for route, grp in daily.groupby("service_rte_num"):
            grp = grp.copy().reset_index(drop=True)
            if len(grp) < 3:
                continue
            
            x = np.arange(len(grp))
            y = grp["avg_load"].values
            
            if np.std(y) == 0:
                slope = 0
            else:
                slope = float(np.polyfit(x, y, 1)[0])
            
            last_avg = grp["rolling_avg_load"].iloc[-1]
            next_7 = last_avg + slope * 7
            
            forecasts.append({
                "service_rte_num": route,
                "last_7day_avg_load": round(last_avg, 2),
                "trend_slope": round(slope, 4),
                "predicted_load_7d": round(max(0, next_7), 2),
                "trend": "↑ Increasing" if slope > 0.05 else ("↓ Decreasing" if slope < -0.05 else "→ Stable")
            })
        
        result = pd.DataFrame(forecasts).sort_values("predicted_load_7d", ascending=False)
        
        summary = (
            "7-day passenger load forecast by route (based on rolling average + linear trend):\n"
            + result.to_string(index=False)
        )
        return {
            "data": result,
            "table": result,
            "summary": summary,
            "chart_type": "bar",
            "x": "service_rte_num",
            "y": "predicted_load_7d",
            "title": "Predicted Passenger Load (Next 7 Days)"
        }