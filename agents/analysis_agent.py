import pandas as pd


class AnalysisAgent:
    def __init__(self, db_manager):
        self.db = db_manager

    def run(self, intent: dict) -> dict:
        t = intent.get("type", "boardings_analysis")
        e = intent.get("entities", {})

        dispatch = {
            "boardings_analysis": self._boardings,
            "crowding_analysis": self._crowding,
            "schedule_adherence": self._schedule_adherence,
            "route_comparison": self._route_comparison,
            "stop_performance": self._stop_performance,
            "geographic": self._geographic,
        }

        fn = dispatch.get(t, self._boardings)
        return fn(e)

    # ── Boardings ──────────────────────────────────────────────────────────
    def _boardings(self, e: dict) -> dict:
        filters = []
        if e.get("day_type"):
            filters.append(f"day_code = '{e['day_type']}'")
        if e.get("route"):
            filters.append(f"service_rte_list LIKE '%{e['route']}%'")

        where = "WHERE " + " AND ".join(filters) if filters else ""

        query = f"""
            SELECT 
                stop_nm,
                SUM(total_boardings) as total_boardings,
                SUM(total_alightings) as total_alightings
            FROM stop_daily
            {where}
            GROUP BY stop_nm
            ORDER BY total_boardings DESC
            LIMIT 15;
        """

        with self.db.get_connection() as conn:
            result = pd.read_sql(query, conn)

        summary = "Top stops by boardings:\n" + result[
            ["stop_nm", "total_boardings", "total_alightings"]
        ].to_string(index=False)
        return {
            "data": result,
            "table": result,
            "summary": summary,
            "chart_type": "bar",
            "x": "stop_nm",
            "y": "total_boardings",
            "title": "Top Stops by Total Boardings",
        }

    # ── Crowding ───────────────────────────────────────────────────────────
    def _crowding(self, e: dict) -> dict:
        filters = []
        if e.get("route"):
            filters.append(f"service_rte_num = '{e['route']}'")
        if e.get("time_period"):
            filters.append(f"LOWER(time_period) = '{e['time_period'].lower()}'")

        where = "WHERE " + " AND ".join(filters) if filters else ""

        query = f"""
            SELECT 
                service_rte_num,
                time_period,
                ROUND(AVG(load_factor), 1) as avg_crowding_pct,
                SUM(CASE WHEN load_factor > 80 THEN 1 ELSE 0 END) as trips_over_80pct,
                COUNT(*) as total_trips
            FROM trips_enriched
            {where}
            GROUP BY service_rte_num, time_period
            ORDER BY avg_crowding_pct DESC;
        """

        with self.db.get_connection() as conn:
            result = pd.read_sql(query, conn)

        summary = "Crowding analysis by route & time period:\n" + result.to_string(
            index=False
        )
        return {
            "data": result,
            "table": result,
            "summary": summary,
            "chart_type": "bar",
            "x": "service_rte_num",
            "y": "avg_crowding_pct",
            "title": "Average Crowding % by Route",
        }

    # ── Schedule Adherence ─────────────────────────────────────────────────
    def _schedule_adherence(self, e: dict) -> dict:
        filters = []
        if e.get("route"):
            filters.append(f"service_rte_num = '{e['route']}'")

        where = "WHERE " + " AND ".join(filters) if filters else ""

        # Calculate delays using timestamp subtraction
        query = f"""
            SELECT 
                service_rte_num,
                ROUND(AVG(EXTRACT(EPOCH FROM (
                    TO_TIMESTAMP(actual_start_time, 'HH12:MI:SS AM') - 
                    TO_TIMESTAMP(sched_start_time, 'HH12:MI:SS AM')
                )) / 60), 2) as avg_delay_min,
                ROUND(100.0 * SUM(
                    CASE WHEN EXTRACT(EPOCH FROM (
                        TO_TIMESTAMP(actual_start_time, 'HH12:MI:SS AM') - 
                        TO_TIMESTAMP(sched_start_time, 'HH12:MI:SS AM')
                    )) / 60 BETWEEN -1 AND 5 THEN 1 ELSE 0 END
                ) / COUNT(*), 1) as on_time_pct,
                COUNT(*) as total_trips
            FROM trips
            {where}
            WHERE actual_start_time IS NOT NULL AND sched_start_time IS NOT NULL
            GROUP BY service_rte_num
            ORDER BY avg_delay_min DESC;
        """

        with self.db.get_connection() as conn:
            result = pd.read_sql(query, conn)

        summary = "Schedule adherence by route:\n" + result.to_string(index=False)
        return {
            "data": result,
            "table": result,
            "summary": summary,
            "chart_type": "bar",
            "x": "service_rte_num",
            "y": "on_time_pct",
            "title": "On-Time Performance % by Route",
        }

    # ── Route Comparison ───────────────────────────────────────────────────
    def _route_comparison(self, e: dict) -> dict:
        filters = []
        if e.get("route"):
            filters.append(f"service_rte_num = '{e['route']}'")

        where = "WHERE " + " AND ".join(filters) if filters else ""

        query = f"""
            SELECT 
                service_rte_num,
                inbd_outbd_cd,
                ROUND(AVG(psngr_boardings), 2) as avg_boardings,
                ROUND(AVG(max_psngr_load), 2) as avg_load,
                COUNT(*) as trips
            FROM trips
            {where}
            GROUP BY service_rte_num, inbd_outbd_cd
            ORDER BY service_rte_num, inbd_outbd_cd;
        """

        with self.db.get_connection() as conn:
            result = pd.read_sql(query, conn)

        summary = "Inbound vs Outbound comparison:\n" + result.to_string(index=False)
        return {
            "data": result,
            "table": result,
            "summary": summary,
            "chart_type": "grouped_bar",
            "x": "service_rte_num",
            "y": "avg_boardings",
            "color": "inbd_outbd_cd",
            "title": "Inbound vs Outbound Avg Boardings",
        }

    # ── Stop Performance ───────────────────────────────────────────────────
    def _stop_performance(self, e: dict) -> dict:
        filters = []
        if e.get("day_type"):
            filters.append(f"day_code = '{e['day_type']}'")

        where = "WHERE " + " AND ".join(filters) if filters else ""

        query = f"""
            SELECT 
                stop_nm,
                SUM(total_boardings) as total_boardings,
                SUM(trips_count) as trips,
                ROUND(SUM(total_boardings)::NUMERIC / NULLIF(SUM(trips_count), 0), 2) as boardings_per_trip
            FROM stop_daily
            {where}
            GROUP BY stop_nm
            ORDER BY total_boardings ASC
            LIMIT 15;
        """

        with self.db.get_connection() as conn:
            result = pd.read_sql(query, conn)

        summary = "Underperforming stops (lowest boardings):\n" + result.to_string(
            index=False
        )
        return {
            "data": result,
            "table": result,
            "summary": summary,
            "chart_type": "bar",
            "x": "stop_nm",
            "y": "total_boardings",
            "title": "Lowest Performing Stops by Boardings",
        }

    # ── Geographic ─────────────────────────────────────────────────────────
    def _geographic(self, e: dict) -> dict:
        filters = []
        if e.get("zone"):
            filters.append(f"sr.gis_regional_fare_zone = '{e['zone']}'")
        if e.get("zip"):
            filters.append(f"sr.gis_zip_cd = '{e['zip']}'")

        where = "WHERE " + " AND ".join(filters) if filters else ""

        query = f"""
            SELECT 
                sr.gis_zip_cd,
                sr.gis_regional_fare_zone,
                SUM(sd.total_boardings) as total_boardings,
                COUNT(DISTINCT sd.stop_id) as stop_count
            FROM stop_daily sd
            JOIN stops_reference sr ON sd.stop_id = sr.stop_id
            {where}
            GROUP BY sr.gis_zip_cd, sr.gis_regional_fare_zone
            ORDER BY total_boardings DESC;
        """

        with self.db.get_connection() as conn:
            result = pd.read_sql(query, conn)

        summary = "Geographic ridership by zone/zip:\n" + result.to_string(index=False)
        return {
            "data": result,
            "table": result,
            "summary": summary,
            "chart_type": "bar",
            "x": "gis_zip_cd",
            "y": "total_boardings",
            "title": "Boardings by ZIP Code",
        }
