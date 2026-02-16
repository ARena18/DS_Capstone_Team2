# query.py

import os
from dotenv import load_dotenv
load_dotenv()

import psycopg2

# --- Initialize connection ---
db_params = {   # connection parameters
    "host": os.getenv("SQL_HOST"),
    "database": os.getenv("SQL_DATABASE"),
    "user": os.getenv("SQL_USERNAME"),
    "password": os.getenv("SQL_PASSWORD"),
    "port": os.getenv("SQL_PORT")
}

def database_version():
    try:
        # Establish connection
        with psycopg2.connect(**db_params) as conn:
            print("Connected to the PostgreSQL server successfully.")

            with conn.cursor() as cur:
                # Execute query
                cur.execute("SELECT version();")
                
                # Fetch result
                db_version = cur.fetchone()
                print(f"PostgreSQL database version: {db_version}")

    except (Exception, psycopg2.Error) as error:
        print(f"Error connecting to the database: {error}")

def operation_period():
    try:
        # Establish connection
        with psycopg2.connect(**db_params) as conn:
            print("Connected to the PostgreSQL server successfully.")

            with conn.cursor() as cur:
                # Execute query
                cur.execute("SELECT MIN(operation_date) AS min_d, MAX(operation_date) AS max_d FROM public.trips;")
                
                # Fetch result
                start_date, end_date = cur.fetchone()
                print(f"Start operation date: {start_date}")
                print(f"End operation date: {end_date}")
                return (start_date, end_date)


    except (Exception, psycopg2.Error) as error:
        print(f"Error connecting to the database: {error}")

database_version()
print()
operation_period()