#!/usr/bin/env python3
from __future__ import annotations
import pandas as pd  # type: ignore
import argparse
from pathlib import Path
from database import DatabaseManager  # type: ignore

"""
etl.py - Load transit datasets into PostgreSQL

Loads:
  1) Trip_level_db.csv      -> public.trips
  2) Stop_level_db.csv      -> public.stop_daily
  3) GIS_stop_cleaned (TSV) -> public.stops_reference

Notes:
- Uses PostgreSQL COPY for speed (via SQLAlchemy raw_connection()).
- Assumes tables already exist (created by transit_schema.sql).
"""


class TransitDataETL:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def _copy_csv_to_table(
        self,
        table_name: str,
        csv_path: Path,
        columns: list[str],
        delimiter: str = ",",
        truncate_first: bool = False,
    ) -> int:
        """
        Fast bulk load using COPY FROM STDIN.
        Returns loaded row count (best-effort via counting lines minus header).
        """
        csv_path = Path(csv_path).expanduser().resolve()
        if not csv_path.exists():
            raise FileNotFoundError(f"File not found: {csv_path}")

        # Best-effort row count (doesn't read whole file into memory)
        # counts lines - 1 header; safe enough for logs
        with csv_path.open("r", encoding="utf-8") as f:
            row_count = sum(1 for _ in f) - 1
        row_count = max(row_count, 0)

        raw_conn = self.db.engine.raw_connection()
        try:
            with raw_conn.cursor() as cur:
                if truncate_first:
                    cur.execute(f"TRUNCATE TABLE {table_name};")

                col_sql = ", ".join(columns)
                copy_sql = f"""
                    COPY {table_name} ({col_sql})
                    FROM STDIN
                    WITH (FORMAT csv, HEADER true, DELIMITER '{delimiter}', QUOTE '"', ESCAPE '"');
                """

                with csv_path.open("r", encoding="utf-8") as f:
                    cur.copy_expert(copy_sql, f)

            raw_conn.commit()
        except Exception:
            raw_conn.rollback()
            raise
        finally:
            raw_conn.close()

        return row_count

    def _table_count(self, table_name: str) -> int:
        q = f"SELECT COUNT(*) AS n FROM {table_name};"
        with self.db.get_connection() as conn:
            return int(pd.read_sql(q, conn).iloc[0]["n"])

    # Loaders
    def load_trips(self, csv_path: str | Path, truncate_first: bool = False) -> None:
        """
        Load Trip_level_db.csv into public.trips.
        """
        trips_cols = [
            "trip_id",
            "service_change_num",
            "service_rte_num",
            "operation_date",
            "sched_start_time",
            "actual_start_time",
            "sched_end_time",
            "actual_end_time",
            "express_local_cd",
            "inbd_outbd_cd",
            "sched_day_type_coded_num",
            "day_code",
            "time_period",
            "psngr_boardings",
            "psngr_alightings",
            "max_psngr_load",
            "crowding_threshold_nbr",
            "load_factor",
        ]

        loaded = self._copy_csv_to_table(
            table_name="public.trips",
            csv_path=Path(csv_path),
            columns=trips_cols,
            delimiter=",",
            truncate_first=truncate_first,
        )
        print(
            f"Trips loaded (attempted rows: {loaded:,})  | table count now: {self._table_count('public.trips'):,}"
        )

    def load_stop_daily(
        self, csv_path: str | Path, truncate_first: bool = False
    ) -> None:
        """
        Loads Stop_level_db.csv into public.stop_daily.
        """
        stop_daily_cols = [
            "operation_date",
            "stop_id",
            "stop_nm",
            "service_rte_list",
            "sched_day_type_coded_num",
            "day_code",
            "day_name",
            "trips_count",
            "total_boardings",
            "total_alightings",
            "avg_departure_load",
            "boardings_per_trip",
            "alightings_per_trip",
        ]

        loaded = self._copy_csv_to_table(
            table_name="public.stop_daily",
            csv_path=Path(csv_path),
            columns=stop_daily_cols,
            delimiter=",",
            truncate_first=truncate_first,
        )
        print(
            f"Stop_daily loaded (attempted rows: {loaded:,}) | table count now: {self._table_count('public.stop_daily'):,}"
        )

    def load_stops_reference(
        self, csv_path: str | Path, truncate_first: bool = False
    ) -> None:
        """Loads GIS_stop_cleaned.csv into public.stops_reference."""
        stops_ref_cols = [
            "change_num",
            "eff_start_date",
            "eff_end_date",
            "stop_id",
            "on_street_nm",
            "gis_regional_fare_zone",
            "gis_zip_cd",
            "gps_latitude",
            "gps_longitude",
        ]

        loaded = self._copy_csv_to_table(
            table_name="public.stops_reference",
            csv_path=Path(csv_path),
            columns=stops_ref_cols,
            delimiter=",",
            truncate_first=truncate_first,
        )
        print(
            f"Stops_reference loaded (attempted rows: {loaded:,}) | table count now: {self._table_count('public.stops_reference'):,}"
        )

    def create_summary_stats(self) -> None:
        with self.db.get_connection() as conn:
            trips = pd.read_sql("SELECT COUNT(*) AS n FROM public.trips;", conn).iloc[
                0
            ]["n"]
            stops = pd.read_sql(
                "SELECT COUNT(*) AS n FROM public.stop_daily;", conn
            ).iloc[0]["n"]
            refs = pd.read_sql(
                "SELECT COUNT(*) AS n FROM public.stops_reference;", conn
            ).iloc[0]["n"]

            trip_dates = pd.read_sql(
                "SELECT MIN(operation_date) AS min_d, MAX(operation_date) AS max_d FROM public.trips;",
                conn,
            )

            stop_dates = pd.read_sql(
                "SELECT MIN(operation_date) AS min_d, MAX(operation_date) AS max_d FROM public.stop_daily;",
                conn,
            )

            unique_routes = pd.read_sql(
                "SELECT COUNT(DISTINCT service_rte_num) AS n FROM public.trips;",
                conn,
            ).iloc[0]["n"]

            unique_stops = pd.read_sql(
                "SELECT COUNT(DISTINCT stop_id) AS n FROM public.stop_daily;",
                conn,
            ).iloc[0]["n"]
        print("\n=== Database Summary ===")
        print(
            f"trips:           {int(trips):,} rows | date range {trip_dates.iloc[0]['min_d']} → {trip_dates.iloc[0]['max_d']}"
        )
        print(
            f"stop_daily:      {int(stops):,} rows | date range {stop_dates.iloc[0]['min_d']} → {stop_dates.iloc[0]['max_d']}"
        )
        print(f"stops_reference: {int(refs):,} rows")
        print(f"unique routes:   {int(unique_routes):,}")
        print(f"unique stops:    {int(unique_stops):,}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-create-tables",
        action="store_true",
        help="Run db.create_tables() before loading",
    )
    parser.add_argument(
        "--truncate", action="store_true", help="Truncate tables before loading"
    )
    parser.add_argument("--trip-csv", required=True, help="Path to Trip_level_db.csv")
    parser.add_argument(
        "--stop-csv", required=True, help="Path to Stop_level_db.csv (stop_daily)"
    )
    parser.add_argument(
        "--gis-csv",
        required=True,
        help="Path to GIS_stop_cleaned.csv (stops_reference)",
    )
    args = parser.parse_args()

    db = DatabaseManager()
    etl = TransitDataETL(db)

    if args.run_create_tables:
        db.create_tables()

    # Load order: reference → stop_daily → trips
    etl.load_stops_reference(args.gis_csv, truncate_first=args.truncate)
    etl.load_stop_daily(args.stop_csv, truncate_first=args.truncate)
    etl.load_trips(args.trip_csv, truncate_first=args.truncate)

    # Validate
    etl.create_summary_stats()


if __name__ == "__main__":
    main()
