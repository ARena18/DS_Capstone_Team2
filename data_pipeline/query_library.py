"""
Transit Planning Query Library
Pre-validated query functions for common planner questions
"""

import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class TransitQueryLibrary:
    """Query functions that the LLM will call"""

    def __init__(self, db_engine: Engine):
        """
        Initialize query library with database connection.

        Args:
            db_engine: SQLAlchemy engine connected to transit_db
        """
        self.engine = db_engine

    def get_top_routes_by_ridership(
        self,
        start_date: str,
        end_date: str,
        top_n: int = 10,
        day_code: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get top N routes ranked by total passenger boardings.

        Planner Questions:
        - "What are the busiest routes?"
        - "Show me top 10 routes by ridership last month"
        - "Which routes have the most passengers on weekdays?"

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            top_n: Number of routes to return (default 10)
            day_code: Optional filter ('WK', 'SA', 'SU', 'HOL')
            direction: Optional filter ('I', 'O')

        Returns:
            DataFrame with: route, total_boardings, total_trips, avg_load_factor
        """
        where_clauses = ["operation_date BETWEEN :start_date AND :end_date"]
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "top_n": int(top_n),
        }

        if day_code is not None:
            where_clauses.append("day_code = :day_code")
            params["day_code"] = day_code

        if direction is not None:
            where_clauses.append("inbd_outbd_cd = :direction")
            params["direction"] = direction

        where_sql = " AND ".join(where_clauses)

        query = text(f"""
            SELECT 
                service_rte_num as route,
                SUM(psngr_boardings) as total_boardings,
                SUM(psngr_alightings) as total_alightings,
                COUNT(*) as total_trips,
                ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load,
                COUNT(*) FILTER (WHERE max_psngr_load > crowding_threshold_nbr) as crowded_trips
            FROM trips
            WHERE {where_sql}
            GROUP BY service_rte_num
            ORDER BY total_boardings DESC
            LIMIT :top_n
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def get_route_ridership_trend(
        self, route_id: str, start_date: str, end_date: str, aggregation: str = "daily"
    ) -> pd.DataFrame:

        agg = (aggregation or "daily").lower().strip()
        if agg not in {"daily", "weekly", "monthly"}:
            agg = "daily"

        if agg == "weekly":
            date_group = "DATE_TRUNC('week', operation_date)::DATE"
        elif agg == "monthly":
            date_group = "DATE_TRUNC('month', operation_date)::DATE"
        else:
            date_group = "operation_date"

        query = text(f"""
            SELECT 
                {date_group} as period,
                SUM(psngr_boardings) as total_boardings,
                SUM(psngr_alightings) as total_alightings,
                COUNT(*) as trip_count,
                ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load,
                COUNT(*) FILTER (WHERE max_psngr_load > crowding_threshold_nbr) as crowded_trips
            FROM trips
            WHERE service_rte_num = :route_id
            AND operation_date BETWEEN :start_date AND :end_date
            GROUP BY {date_group}
            ORDER BY period
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {
                    "route_id": str(route_id).strip(),
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def get_busiest_stops(
        self,
        start_date: str,
        end_date: str,
        route_id: Optional[str] = None,
        top_n: int = 20,
        metric: str = "boardings",
    ) -> pd.DataFrame:
        """
        Identify stops with highest boarding/alighting activity.

        Planner Questions:
        - "Which stops have the most boardings?"
        - "Show me the top 20 stops for Route 40"
        - "What are the busiest stops in the system?"

        Args:
            start_date: Start date
            end_date: End date
            route_id: Optional route filter
            top_n: Number of stops to return
            metric: 'boardings' or 'alightings'

        Returns:
            DataFrame with stop activity metrics
        """
        m = (metric or "boardings").lower().strip()
        if m not in {"boardings", "alightings"}:
            m = "boardings"

        order_col = "total_boardings" if metric == "boardings" else "total_alightings"

        top_n = int(top_n)

        query = text(f"""
            SELECT 
                sd.stop_id,
                sd.stop_nm,
                SUM(sd.total_boardings) as total_boardings,
                SUM(sd.total_alightings) as total_alightings,
                COUNT(DISTINCT sd.operation_date) as days_with_data,
                ROUND(AVG(sd.avg_departure_load), 2) as avg_departure_load,
                SUM(sd.trips_count) as total_trips
            FROM stop_daily sd
            WHERE sd.operation_date BETWEEN :start_date AND :end_date
                AND (:route_id IS NULL OR sd.service_rte_list LIKE '%' || :route_id || '%')
            GROUP BY sd.stop_id, sd.stop_nm
            ORDER BY {order_col} DESC
            LIMIT :top_n
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "route_id": route_id,
                    "top_n": top_n,
                },
            )
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            return df

    def analyze_service_change_impact(
        self, route_id: str, change_date: str, window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Compare ridership before/after a service change.

        Planner Questions:
        - "How did the September service change affect Route 40?"
        - "What was the impact of the schedule adjustment?"
        - "Did ridership improve after we increased frequency?"

        Args:
            route_id: Route identifier
            change_date: Date of service change (YYYY-MM-DD)
            window_days: Days before/after to compare (default 30)

        Returns:
            Dictionary with before/after metrics and % change
        """
        change_dt = datetime.strptime(change_date, "%Y-%m-%d").date()
        before_start = change_dt - timedelta(days=window_days)
        before_end = change_dt - timedelta(days=1)
        after_start = change_dt
        after_end = change_dt + timedelta(days=window_days)

        query = text("""
            SELECT 
                COUNT(*) as trips,
                COUNT(DISTINCT operation_date) as days,
                ROUND(AVG(psngr_boardings), 2) as avg_boardings,
                SUM(psngr_boardings) as total_boardings,
                ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load,
                COUNT(*) FILTER (
                    WHERE max_psngr_load > crowding_threshold_nbr
                ) as crowded_trips
            FROM trips
            WHERE service_rte_num = :route_id
            AND operation_date BETWEEN :start_date AND :end_date
            AND day_code = 'WK'
            AND max_psngr_load IS NOT NULL
            AND crowding_threshold_nbr IS NOT NULL
        """)

        with self.engine.connect() as conn:
            # Before period
            before_result = conn.execute(
                query,
                {
                    "route_id": route_id,
                    "start_date": before_start,
                    "end_date": before_end,
                },
            ).fetchone()

            # After period
            after_result = conn.execute(
                query,
                {
                    "route_id": route_id,
                    "start_date": after_start,
                    "end_date": after_end,
                },
            ).fetchone()

        # Calculate changes
        before_avg = float(before_result[2]) if before_result[2] else 0
        after_avg = float(after_result[2]) if after_result[2] else 0

        boardings_pct_change = (
            ((after_avg - before_avg) / before_avg * 100) if before_avg > 0 else 0
        )

        before_load = float(before_result[4]) if before_result[4] else 0
        after_load = float(after_result[4]) if after_result[4] else 0
        load_change = after_load - before_load

        return {
            "route_id": route_id,
            "change_date": change_date,
            "window_days": window_days,
            "before_period": {
                "start_date": str(before_start),
                "end_date": str(before_end),
                "trips": before_result[0],
                "days": before_result[1],
                "avg_boardings_per_trip": before_result[2],
                "total_boardings": before_result[3],
                "avg_max_psngr_load": before_result[4],
                "crowded_trips": before_result[5],
            },
            "after_period": {
                "start_date": str(after_start),
                "end_date": str(after_end),
                "trips": after_result[0],
                "days": after_result[1],
                "avg_boardings_per_trip": after_result[2],
                "total_boardings": after_result[3],
                "avg_max_psngr_load": after_result[4],
                "crowded_trips": after_result[5],
            },
            "impact": {
                "boardings_change": round(after_avg - before_avg, 2),
                "boardings_pct_change": round(boardings_pct_change, 2),
                "load_change": round(load_change, 2),
                "direction": "increase" if boardings_pct_change > 0 else "decrease",
                "significant": abs(boardings_pct_change) > 5,  # Flag if >5% change
            },
        }

    def get_overcrowded_routes(
        self,
        service_change_num: Optional[str] = None,
        time_period: Optional[str] = None,
        top_n: int = 10,
    ) -> pd.DataFrame:
        """
        Identify routes with highest crowding using KCM's definition (Trips are identified as overcrowded
        if they have average maximum passenger loads higher than the passenger load threshold for the
        entire service change period.)

        Note:
        Trip pattern = unique combination of (route, direction, start_time, day_code)
        This matches KCM's methodology of averaging per trip pattern, not per individual trip.

        Planner Questions:
        - "Which routes are most crowded for last service change?"
        - "Show me routes exceeding capacity during AM Peak"
        - "What routes have the worst crowding?"
        """
        where_clauses = []
        params = {"top_n": int(top_n)}

        if service_change_num is not None:
            where_clauses.append("service_change_num = :service_change_num")
            params["service_change_num"] = service_change_num
        else:
            raise ValueError("Must provide service_change_num")

        if time_period is not None:
            where_clauses.append("time_period = :time_period")
            params["time_period"] = time_period

        where_sql = " AND ".join(where_clauses)

        query = text(f"""
            WITH trip_patterns AS (
                SELECT
                    service_rte_num,
                    inbd_outbd_cd,
                    sched_start_time,
                    service_change_num,
                    day_code,
                    AVG(max_psngr_load) AS avg_max_load,
                    AVG(crowding_threshold_nbr) AS threshold,
                    AVG(max_psngr_load) - AVG(crowding_threshold_nbr) as excess_load
                FROM trips
                WHERE {where_sql}
                GROUP BY
                    service_rte_num,
                    inbd_outbd_cd,
                    sched_start_time,
                    service_change_num,
                    day_code
            ),
            overcrowded_patterns AS (
                SELECT *
                FROM trip_patterns
                WHERE avg_max_load > threshold
            ),
            route_summary AS (
            SELECT
                tp.service_rte_num,
                COUNT(DISTINCT 
                    CONCAT(tp.inbd_outbd_cd, '|', tp.sched_start_time)
                ) as total_trips_count,
                COUNT(DISTINCT 
                    CASE WHEN op.service_rte_num IS NOT NULL 
                    THEN CONCAT(tp.inbd_outbd_cd, '|', tp.sched_start_time)
                    END
                ) as overcrowded_trips,
                ROUND(AVG(CASE WHEN op.service_rte_num IS NOT NULL 
                          THEN op.avg_max_load END), 2) as avg_max_load_overcrowded,
                ROUND(AVG(CASE WHEN op.service_rte_num IS NOT NULL 
                          THEN op.threshold END), 2) as avg_threshold_overcrowded,
                ROUND(AVG(CASE WHEN op.service_rte_num IS NOT NULL 
                          THEN op.excess_load END), 2) as avg_excess_load
            FROM trip_patterns tp
            LEFT JOIN overcrowded_patterns op 
                ON tp.service_rte_num = op.service_rte_num
                AND tp.inbd_outbd_cd = op.inbd_outbd_cd
                AND tp.sched_start_time = op.sched_start_time
                AND tp.service_change_num = op.service_change_num
            GROUP BY tp.service_rte_num
        )
        SELECT
            service_rte_num AS route,
            overcrowded_trips,
            total_trips_count,
            ROUND(100.0 * overcrowded_trips / NULLIF(total_trips_count, 0), 2) as pct_overcrowded,
            avg_max_load_overcrowded as avg_max_load,
            avg_threshold_overcrowded as avg_threshold,
            avg_excess_load
        FROM route_summary
        WHERE overcrowded_trips > 0  -- Only show routes with overcrowding
        ORDER BY overcrowded_trips DESC, pct_overcrowded DESC
        LIMIT :top_n
    """)

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def compare_routes(
        self, route_ids: list, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        Compare multiple routes side-by-side.

        Planner Questions:
        - "Compare Route 40 and Route 7"
        - "How do Routes 1, 2, and 3 compare?"
        """
        query = text("""
            SELECT 
                service_rte_num as route,
                SUM(psngr_boardings) as total_boardings,
                SUM(psngr_alightings) as total_alightings,
                COUNT(*) as total_trips,
                ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load,
                COUNT(*) FILTER (WHERE max_psngr_load > crowding_threshold_nbr) as crowded_trips,
                ROUND(100.0 * COUNT(*) FILTER (WHERE max_psngr_load > crowding_threshold_nbr) / COUNT(*), 2) as pct_crowded
            FROM trips
            WHERE service_rte_num = ANY(:route_ids)
                AND operation_date BETWEEN :start_date AND :end_date
            GROUP BY service_rte_num
            ORDER BY total_boardings DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {
                    "route_ids": route_ids,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def identify_declining_routes(
        self,
        comparison_months: int = 3,
        threshold_pct: float = -10.0,
        min_trips: int = 100,
    ) -> pd.DataFrame:
        """
        Identify routes with significant ridership decline.

        Planner Questions:
        - "Which routes are losing ridership?"
        - "Show me declining routes over the last 3 months"
        - "What routes need attention?"
        """
        # Get latest date from database
        summary = self.get_summary()
        latest_date = datetime.strptime(summary["latest_date"], "%Y-%m-%d").date()

        # Calculate date ranges
        recent_start = latest_date - timedelta(days=comparison_months * 30)
        previous_start = recent_start - timedelta(days=comparison_months * 30)
        previous_end = recent_start - timedelta(days=1)

        query = text("""
            WITH recent_period AS (
                SELECT 
                    service_rte_num,
                    COUNT(*) as trip_count,
                    ROUND(AVG(psngr_boardings), 2) as avg_boardings,
                    ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load
                FROM trips
                WHERE operation_date BETWEEN :recent_start AND :latest_date
                    AND day_code = 'WK'
                GROUP BY service_rte_num
            ),
            previous_period AS (
                SELECT 
                    service_rte_num,
                    ROUND(AVG(psngr_boardings), 2) as avg_boardings,
                    ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load
                FROM trips
                WHERE operation_date BETWEEN :previous_start AND :previous_end
                    AND day_code = 'WK'
                GROUP BY service_rte_num
            )
            SELECT 
                r.service_rte_num as route,
                r.trip_count,
                p.avg_boardings as previous_avg_boardings,
                r.avg_boardings as recent_avg_boardings,
                ROUND(((r.avg_boardings - p.avg_boardings) / p.avg_boardings * 100), 2) as boardings_pct_change,
                p.avg_max_psngr_load as previous_load_factor,
                r.avg_max_psngr_load as recent_load_factor,
                ROUND((r.avg_max_psngr_load - p.avg_max_psngr_load), 2) as max_psngr_load_change
            FROM recent_period r
            JOIN previous_period p ON r.service_rte_num = p.service_rte_num
            WHERE r.trip_count >= :min_trips
                AND p.avg_boardings > 0
                AND ((r.avg_boardings - p.avg_boardings) / p.avg_boardings * 100) < :threshold_pct
            ORDER BY boardings_pct_change ASC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {
                    "latest_date": latest_date,
                    "recent_start": recent_start,
                    "previous_start": previous_start,
                    "previous_end": previous_end,
                    "threshold_pct": threshold_pct,
                    "min_trips": min_trips,
                },
            )
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def get_crowding_by_time_period(
        self,
        route_id: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        Analyze crowding patterns by time of day.

        Planner Questions:
        - "When are routes most crowded?"
        - "Show me crowding by time period for Route 40"
        """
        where_clauses = ["operation_date BETWEEN :start_date AND :end_date"]
        params = {"start_date": start_date, "end_date": end_date, "route_id": route_id}

        if route_id is not None:
            where_clauses.append("service_rte_num = :route_id")

        where_sql = " AND ".join(where_clauses)

        query = text(f"""
            SELECT 
                time_period,
                COUNT(*) as total_trips,
                COUNT(*) FILTER (WHERE max_psngr_load > crowding_threshold_nbr) as crowded_trips,
                ROUND(100.0 * COUNT(*) FILTER (WHERE max_psngr_load > crowding_threshold_nbr) / COUNT(*), 2) as pct_crowded,
                ROUND(AVG(max_psngr_load),2) as avg_max_psngr_load,
                ROUND(AVG(psngr_boardings), 2) as avg_boardings
            FROM trips
            WHERE {where_sql}
            GROUP BY time_period
            ORDER BY pct_crowded DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def get_route_by_direction(
        self, route_id: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        Compare inbound vs outbound performance for a route.

        Planner Questions:
        - "How does inbound vs outbound ridership compare for Route 40?"
        - "Show me directional ridership for Route 7"
        """
        query = text("""
            SELECT 
                inbd_outbd_cd as direction,
                CASE 
                    WHEN inbd_outbd_cd = 'I' THEN 'Inbound'
                    WHEN inbd_outbd_cd = 'O' THEN 'Outbound'
                    ELSE 'Other'
                END as direction_label,
                SUM(psngr_boardings) as total_boardings,
                COUNT(*) as total_trips,
                ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load
            FROM trips
            WHERE service_rte_num = :route_id
                AND operation_date BETWEEN :start_date AND :end_date
            GROUP BY inbd_outbd_cd
            ORDER BY total_boardings DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query,
                {"route_id": route_id, "start_date": start_date, "end_date": end_date},
            )
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    def get_ridership_by_day_type(
        self,
        route_id: Optional[str] = None,
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        Analyze ridership by day type (Weekday, Saturday, Sunday, Holiday).

        Planner Questions:
        - "How does ridership vary by day type?"
        - "Compare weekday, Saturday, and Sunday ridership"
        """
        where_clauses = ["operation_date BETWEEN :start_date AND :end_date"]
        params = {"start_date": start_date, "end_date": end_date, "route_id": route_id}

        if route_id is not None:
            where_clauses.append("service_rte_num = :route_id")

        where_sql = " AND ".join(where_clauses)

        query = text(f"""
            SELECT 
                day_code,
                CASE 
                    WHEN day_code = 'WK' THEN 'Weekday'
                    WHEN day_code = 'SA' THEN 'Saturday'
                    WHEN day_code = 'SU' THEN 'Sunday'
                    WHEN day_code = 'HOL' THEN 'Holiday'
                END as day_type,
                COUNT(DISTINCT operation_date) as days,
                COUNT(*) as total_trips,
                SUM(psngr_boardings) as total_boardings,
                ROUND(AVG(psngr_boardings), 2) as avg_boardings_per_trip,
                ROUND(AVG(max_psngr_load), 2) as avg_max_psngr_load
            FROM trips
            WHERE {where_sql}
            GROUP BY day_code
            ORDER BY total_boardings DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            return pd.DataFrame(result.fetchall(), columns=result.keys())

    # Helper funtion
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of available data in the database.

        Returns:
            Dictionary with data availability info
        """
        query = text("""
            SELECT 
                MIN(operation_date) as earliest_date,
                MAX(operation_date) as latest_date,
                COUNT(DISTINCT operation_date) as distinct_dates,
                COUNT(DISTINCT service_rte_num) as unique_routes,
                COUNT(*) as total_trips
            FROM trips
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()

            return {
                "earliest_date": str(result[0]),
                "latest_date": str(result[1]),
                "distinct_dates": result[2],
                "unique_routes": result[3],
                "total_trips": result[4],
            }


# ================================================================
# TESTING EXAMPLE
# ================================================================

if __name__ == "__main__":
    """
    Test function of TransitQueryLibrary
    """
    from sqlalchemy import create_engine

    # Create database connection
    DATABASE_URL = "postgresql+psycopg://postgres@localhost:5432/transit_db"
    # print("DATABASE_URL =", DATABASE_URL)
    engine = create_engine(DATABASE_URL)

    # Initialize query library
    query_lib = TransitQueryLibrary(engine)

    # Test 1: Get data summary
    print("=== Trip Data Summary ===")
    summary = query_lib.get_summary()
    print(f"Date Range: {summary['earliest_date']} to {summary['latest_date']}")
    print(f"Unique Routes: {summary['unique_routes']}")
    print(f"Total Trips: {summary['total_trips']:,}")

    # Test 2: Top routes
    print("\n=== Top 10 Routes by Ridership ===")
    top_routes = query_lib.get_top_routes_by_ridership(
        start_date="2025-01-01",
        end_date="2025-01-31",
        top_n=10,
        day_code="WK",  # optional
    )
    print(top_routes)

    # Test 3: Service change impact
    print("\n=== Service Change Impact (Route 40) ===")
    impact = query_lib.analyze_service_change_impact(
        route_id="40", change_date="2025-01-15", window_days=14
    )
    print(f"Before: {impact['before_period']['avg_boardings_per_trip']} avg boardings")
    print(f"After: {impact['after_period']['avg_boardings_per_trip']} avg boardings")
    print(f"Change: {impact['impact']['boardings_pct_change']}%")
