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
        direction: Optional[str] = None
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
            direction: Optional filter ('I', 'O', '0')
        
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

        sql = f"""
            SELECT 
                service_rte_num as route,
                SUM(psngr_boardings) as total_boardings,
                SUM(psngr_alightings) as total_alightings,
                COUNT(*) as total_trips,
                ROUND(AVG(load_factor), 2) as avg_load_factor,
                COUNT(*) FILTER (WHERE is_crowded = TRUE) as crowded_trips
            FROM trips_enriched
            WHERE {where_sql}
            GROUP BY service_rte_num
            ORDER BY total_boardings DESC
            LIMIT :top_n
        """

        query = text(sql)

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        
    def get_route_ridership_trend(
        self,
        route_id: str,
        start_date: str,
        end_date: str,
        aggregation: str = 'daily'
    ) -> pd.DataFrame:
        """
        Get ridership trend for a specific route over time.
        
        Planner Questions:
        - "Show me ridership trends for Route 40"
        - "How has Route 7 ridership changed over the last 6 months?"
        - "Give me weekly ridership for Route E Line"
        
        Args:
            route_id: Route identifier (e.g., '40', '7', 'E Line')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            aggregation: 'daily', 'weekly', or 'monthly'
        
        Returns:
            DataFrame with: period, total_boardings, trip_count, avg_load_factor
        """
        # Build aggregation based on parameter
        if aggregation == 'weekly':
            date_group = "DATE_TRUNC('week', operation_date)::DATE"
        elif aggregation == 'monthly':
            date_group = "DATE_TRUNC('month', operation_date)::DATE"
        else:
            date_group = "operation_date"
        
        query = text(f"""
            SELECT 
                {date_group} as period,
                SUM(psngr_boardings) as total_boardings,
                SUM(psngr_alightings) as total_alightings,
                COUNT(*) as trip_count,
                ROUND(AVG(load_factor), 2) as avg_load_factor,
                COUNT(*) FILTER (WHERE is_crowded = TRUE) as crowded_trips
            FROM trips_enriched
            WHERE service_rte_num = :route_id
                AND operation_date BETWEEN :start_date AND :end_date
            GROUP BY {date_group}
            ORDER BY period
        """)
        
        with self.engine.connect() as conn:
            result = conn.execute(query, {
                'route_id': route_id,
                'start_date': start_date,
                'end_date': end_date
            })
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            return df
    
    def get_busiest_stops(
        self,
        start_date: str,
        end_date: str,
        route_id: Optional[str] = None,
        top_n: int = 20,
        metric: str = 'boardings'
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
        order_col = 'total_boardings' if metric == 'boardings' else 'total_alightings'
        
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
            result = conn.execute(query, {
                'start_date': start_date,
                'end_date': end_date,
                'route_id': route_id,
                'top_n': top_n
            })
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            return df
        
    def analyze_service_change_impact(
        self,
        route_id: str,
        change_date: str,
        window_days: int = 30
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
        change_dt = datetime.strptime(change_date, '%Y-%m-%d').date()
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
                ROUND(AVG(load_factor), 2) as avg_load_factor,
                COUNT(*) FILTER (WHERE is_crowded = TRUE) as crowded_trips
            FROM trips_enriched
            WHERE service_rte_num = :route_id
                AND operation_date BETWEEN :start_date AND :end_date
                AND day_code = 'WK'  -- Compare same day types
        """)
        
        with self.engine.connect() as conn:
            # Before period
            before_result = conn.execute(query, {
                'route_id': route_id,
                'start_date': before_start,
                'end_date': before_end
            }).fetchone()
            
            # After period
            after_result = conn.execute(query, {
                'route_id': route_id,
                'start_date': after_start,
                'end_date': after_end
            }).fetchone()
        
        # Calculate changes
        before_avg = float(before_result[2]) if before_result[2] else 0
        after_avg = float(after_result[2]) if after_result[2] else 0
        
        boardings_pct_change = ((after_avg - before_avg) / before_avg * 100) if before_avg > 0 else 0
        
        before_load = float(before_result[4]) if before_result[4] else 0
        after_load = float(after_result[4]) if after_result[4] else 0
        load_change = after_load - before_load
        
        return {
            'route_id': route_id,
            'change_date': change_date,
            'window_days': window_days,
            'before_period': {
                'start_date': str(before_start),
                'end_date': str(before_end),
                'trips': before_result[0],
                'days': before_result[1],
                'avg_boardings_per_trip': before_result[2],
                'total_boardings': before_result[3],
                'avg_load_factor': before_result[4],
                'crowded_trips': before_result[5]
            },
            'after_period': {
                'start_date': str(after_start),
                'end_date': str(after_end),
                'trips': after_result[0],
                'days': after_result[1],
                'avg_boardings_per_trip': after_result[2],
                'total_boardings': after_result[3],
                'avg_load_factor': after_result[4],
                'crowded_trips': after_result[5]
            },
            'impact': {
                'boardings_change': round(after_avg - before_avg, 2),
                'boardings_pct_change': round(boardings_pct_change, 2),
                'load_factor_change': round(load_change, 2),
                'direction': 'increase' if boardings_pct_change > 0 else 'decrease',
                'significant': abs(boardings_pct_change) > 5  # Flag if >5% change
            }
        }

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
                'earliest_date': str(result[0]),
                'latest_date': str(result[1]),
                'distinct_dates': result[2],
                'unique_routes': result[3],
                'total_trips': result[4]
            }


# ================================================================
# USAGE EXAMPLE
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
        start_date='2025-01-01',
        end_date='2025-01-31',
        top_n=10,
        day_code='WK' #optional
    )
    print(top_routes)
    
    # Test 3: Service change impact
    print("\n=== Service Change Impact (Route 40) ===")
    impact = query_lib.analyze_service_change_impact(
        route_id='40',
        change_date='2025-01-15',
        window_days=14
    )
    print(f"Before: {impact['before_period']['avg_boardings_per_trip']} avg boardings")
    print(f"After: {impact['after_period']['avg_boardings_per_trip']} avg boardings")
    print(f"Change: {impact['impact']['boardings_pct_change']}%")
