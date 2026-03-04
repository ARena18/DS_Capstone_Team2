# query_info.py

import os
from dotenv import load_dotenv

load_dotenv()

import psycopg2

# --- Declare schema string to prompt LLM
SCHEMA = """
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS stop_daily CASCADE;
DROP TABLE IF EXISTS stops_reference CASCADE;

-- ================================================================
-- TABLE: trips
-- Description: Raw trip-level operational data from King County Metro
-- Source: Trip-level dataset from APC (Automated Passenger Counter)
-- ================================================================
CREATE TABLE trips (
    -- Identifiers
    trip_id BIGINT NOT NULL,
	operation_date DATE NOT NULL,
    service_change_num VARCHAR(10) NOT NULL,
    service_rte_num VARCHAR(20) NOT NULL,
    
    -- Time Information
    sched_start_time text NOT NULL,
    actual_start_time text,
    sched_end_time text NOT NULL,
    actual_end_time text,
    
    -- Trip Characteristics
    express_local_cd CHAR(1) NOT NULL CHECK (express_local_cd IN ('E', 'L')),
    inbd_outbd_cd CHAR(1) NOT NULL CHECK (inbd_outbd_cd IN ('I', 'O', '0')),
    
    -- Day Type Information
    sched_day_type_coded_num SMALLINT NOT NULL CHECK (sched_day_type_coded_num IN (0, 1, 2, 6)),
    day_code VARCHAR(3) NOT NULL CHECK (day_code IN ('WK', 'SA', 'SU', 'HOL')),
    time_period VARCHAR(20) NOT NULL,
    
    -- Ridership Metrics
    psngr_boardings NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (psngr_boardings >= 0),
    psngr_alightings NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (psngr_alightings >= 0),
    max_psngr_load NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (max_psngr_load >= 0),
    
    -- Capacity Metrics
    crowding_threshold_nbr INTEGER NOT NULL CHECK (crowding_threshold_nbr > 0),

	CONSTRAINT pk_trips PRIMARY KEY (trip_id, operation_date)
);

-- Indexes for common query patterns
CREATE INDEX idx_trips_operation_date ON trips(operation_date);
CREATE INDEX idx_trips_route_date ON trips(service_rte_num, operation_date);
CREATE INDEX idx_trips_route ON trips(service_rte_num);

-- ================================================================
-- TABLE: stop_daily
-- Description: Daily aggregated stop-level ridership
-- Source: Stop-level dataset (pre-aggregated by King County Metro)
-- ================================================================
CREATE TABLE stop_daily (
	-- Identifiers
	operation_date DATE NOT NULL,
    stop_id VARCHAR(20) NOT NULL,
	stop_nm VARCHAR(200),
    service_rte_list VARCHAR(50) NOT NULL,

	-- Date Information
    sched_day_type_coded_num SMALLINT NOT NULL,
    day_code VARCHAR(3) NOT NULL,
    day_name VARCHAR(10) NOT NULL,

	-- Ridership Metrics
    trips_count INTEGER NOT NULL DEFAULT 0,
    total_boardings INTEGER NOT NULL DEFAULT 0,
    total_alightings INTEGER NOT NULL DEFAULT 0,
    avg_departure_load NUMERIC(10, 2) DEFAULT 0,
	
    CONSTRAINT pk_stop_daily PRIMARY KEY (stop_id, operation_date, service_rte_list)
);

-- Indexes for common query patterns
CREATE INDEX idx_stop_daily_date ON stop_daily(stop_id, operation_date);
CREATE INDEX idx_stop_daily_stop ON stop_daily(stop_id);

-- ================================================================
-- TABLE: stops_reference
-- Description: GIS transit stop master reference data
-- Source: GIS_transit_stop.xlsx from King County Metro
-- ================================================================
CREATE TABLE stops_reference (
    stop_id VARCHAR(20) NOT NULL,
    eff_start_date DATE NOT NULL,
    eff_end_date DATE,

	-- Location information
    on_street_nm VARCHAR(200),
    gps_latitude NUMERIC(10, 7),
    gps_longitude NUMERIC(11, 7),
    gis_zip_cd VARCHAR(10),
	gis_regional_fare_zone VARCHAR(10),
	
    change_num INTEGER,

	CONSTRAINT pk_stops_reference PRIMARY KEY (stop_id, eff_start_date),
	
    CHECK (eff_end_date IS NULL OR eff_end_date >= eff_start_date),
    CHECK (gps_latitude IS NULL OR gps_latitude BETWEEN -90 AND 90),
    CHECK (gps_longitude IS NULL OR gps_longitude BETWEEN -180 AND 180)
);

-- Create index
CREATE INDEX idx_stops_ref_lookup ON stops_reference(stop_id, eff_start_date, eff_end_date);
CREATE INDEX idx_stops_ref_zip ON stops_reference(gis_zip_cd);
"""


OLD_SCHEMA = """
DROP TABLE IF EXISTS trips CASCADE;
DROP TABLE IF EXISTS stop_daily CASCADE;
DROP TABLE IF EXISTS stops_reference CASCADE;

-- ================================================================
-- TABLE: trips
-- Description: Raw trip-level operational data from King County Metro
-- Source: Trip-level dataset from APC (Automated Passenger Counter)
-- ================================================================
CREATE TABLE trips (
    -- Identifiers
    trip_id BIGINT NOT NULL,
	operation_date DATE NOT NULL,
    service_change_num VARCHAR(10) NOT NULL,
    service_rte_num VARCHAR(20) NOT NULL,
    
    -- Time Information
    sched_start_time text NOT NULL,
    actual_start_time text,
    sched_end_time text NOT NULL,
    actual_end_time text,
    
    -- Trip Characteristics
    express_local_cd CHAR(1) NOT NULL CHECK (express_local_cd IN ('E', 'L')),
    -- rows with the value 'E' are express routes and rows with the value 'L' are local routes
    inbd_outbd_cd CHAR(1) NOT NULL CHECK (inbd_outbd_cd IN ('I', 'O', '0')),
    -- rows with the value 'I' are inbound routes and rows with the value 'O' are outbound routes
    
    -- Day Type Information
    sched_day_type_coded_num SMALLINT NOT NULL CHECK (sched_day_type_coded_num IN (0, 1, 2, 6)),
    day_code VARCHAR(3) NOT NULL CHECK (day_code IN ('WK', 'SA', 'SU', 'HOL')),
    time_period VARCHAR(20) NOT NULL,
    
    -- Ridership Metrics
    psngr_boardings NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (psngr_boardings >= 0),
    psngr_alightings NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (psngr_alightings >= 0),
    max_psngr_load NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (max_psngr_load >= 0),
    
    -- Capacity Metrics
    crowding_threshold_nbr INTEGER NOT NULL CHECK (crowding_threshold_nbr > 0),

	CONSTRAINT pk_trips PRIMARY KEY (trip_id, operation_date)
);

-- Indexes for common query patterns
CREATE INDEX idx_trips_operation_date ON trips(operation_date);
CREATE INDEX idx_trips_route_date ON trips(service_rte_num, operation_date);
CREATE INDEX idx_trips_route ON trips(service_rte_num);

-- ================================================================
-- TABLE: stop_daily
-- Description: Daily aggregated stop-level ridership
-- Source: Stop-level dataset (pre-aggregated by King County Metro)
-- ================================================================
CREATE TABLE stop_daily (
	-- Identifiers
	operation_date DATE NOT NULL,
    stop_id VARCHAR(20) NOT NULL,
	stop_nm VARCHAR(200),
    service_rte_list VARCHAR(50) NOT NULL,

	-- Date Information
    sched_day_type_coded_num SMALLINT NOT NULL,
    day_code VARCHAR(3) NOT NULL,
    day_name VARCHAR(10) NOT NULL,

	-- Ridership Metrics
    trips_count INTEGER NOT NULL DEFAULT 0,
    total_boardings INTEGER NOT NULL DEFAULT 0,
    total_alightings INTEGER NOT NULL DEFAULT 0,
    avg_departure_load NUMERIC(10, 2) DEFAULT 0,
	
    CONSTRAINT pk_stop_daily PRIMARY KEY (stop_id, operation_date, service_rte_list)
);

-- Indexes for common query patterns
CREATE INDEX idx_stop_daily_date ON stop_daily(stop_id, operation_date);
CREATE INDEX idx_stop_daily_stop ON stop_daily(stop_id);

-- ================================================================
-- TABLE: stops_reference
-- Description: GIS transit stop master reference data
-- Source: GIS_transit_stop.xlsx from King County Metro
-- ================================================================
CREATE TABLE stops_reference (
    stop_id VARCHAR(20) NOT NULL,
    eff_start_date DATE NOT NULL,
    eff_end_date DATE,

	-- Location information
    on_street_nm VARCHAR(200),
    gps_latitude NUMERIC(10, 7),
    gps_longitude NUMERIC(11, 7),
    gis_zip_cd VARCHAR(10),
	gis_regional_fare_zone VARCHAR(10),
	
    change_num INTEGER,

	CONSTRAINT pk_stops_reference PRIMARY KEY (stop_id, eff_start_date),
	
    CHECK (eff_end_date IS NULL OR eff_end_date >= eff_start_date),
    CHECK (gps_latitude IS NULL OR gps_latitude BETWEEN -90 AND 90),
    CHECK (gps_longitude IS NULL OR gps_longitude BETWEEN -180 AND 180)
);

-- Create index
CREATE INDEX idx_stops_ref_lookup ON stops_reference(stop_id, eff_start_date, eff_end_date);
CREATE INDEX idx_stops_ref_zip ON stops_reference(gis_zip_cd);

-- ================================================================
-- VIEWS: Calculated Fields as Database Views
-- These provide the calculated fields without storing them
-- ================================================================

-- View: trips_enriched
-- Adds calculated temporal and performance fields to trips

CREATE OR REPLACE VIEW trips_enriched AS
SELECT 
    t.*,
    
    -- Temporal calculations (derived from operation_date)
    EXTRACT(MONTH FROM t.operation_date)::SMALLINT as month,
    EXTRACT(DAY FROM t.operation_date)::SMALLINT as day,
    EXTRACT(DOW FROM t.operation_date)::SMALLINT as day_of_week,  -- 0=Sunday, 6=Saturday
	
    -- Weekend flag
    CASE 
        WHEN EXTRACT(DOW FROM t.operation_date) IN (0, 6) THEN TRUE 
        ELSE FALSE 
    END as is_weekend,
    
    -- Performance calculations
    ROUND((t.max_psngr_load::NUMERIC / t.crowding_threshold_nbr * 100), 2) as load_factor,
    
    -- Crowding flag (load factor > 100%)
    CASE 
        WHEN t.max_psngr_load > t.crowding_threshold_nbr THEN TRUE 
       ELSE FALSE 
    END as is_crowded
	
FROM trips t;

-- View: stop_daily_enriched
-- Adds calculated fields to stop_daily
CREATE OR REPLACE VIEW stop_daily_enriched AS
SELECT 
    sd.*,
    
    -- Temporal calculations
    EXTRACT(MONTH FROM sd.operation_date)::SMALLINT as month,
    EXTRACT(WEEK FROM sd.operation_date)::SMALLINT as week,
    EXTRACT(DOW FROM sd.operation_date)::SMALLINT as day_of_week,
    
    -- Weekend flag
    CASE 
        WHEN EXTRACT(DOW FROM sd.operation_date) IN (0, 6) THEN TRUE 
        ELSE FALSE 
    END as is_weekend,
    
    -- Per-trip metrics
    CASE 
        WHEN sd.trips_count > 0 THEN ROUND(sd.total_boardings::NUMERIC / sd.trips_count, 4)
        ELSE 0 
    END as boardings_per_trip,
    
    CASE 
        WHEN sd.trips_count > 0 THEN ROUND(sd.total_alightings::NUMERIC / sd.trips_count, 4)
        ELSE 0 
    END as alightings_per_trip

FROM stop_daily sd;
"""

# --- Establish connection ---
db_params = {  # connection parameters
    "host": os.getenv("SQL_HOST"),
    "database": os.getenv("SQL_DATABASE"),
    "user": os.getenv("SQL_USERNAME"),
    "password": os.getenv("SQL_PASSWORD"),
    "port": os.getenv("SQL_PORT"),
}


def query_db(query_statement):
    try:
        # Establish connection
        with psycopg2.connect(**db_params) as conn:
            print("\nConnected to the PostgreSQL server successfully.")

            with conn.cursor() as cur:
                # Execute query
                cur.execute(query_statement)

                # Fetch result
                result = cur.fetchall()
                return result

    except (Exception, psycopg2.Error) as error:
        print(f"Error connecting to the database: {error}")
        return f"Error: {error}"


"""
                else:
                    print("Attempting to generate a query...")
                    queryInstructions = "You are a helpful assistant who only answers about King County Metro. There is a database with the folowing schema: " + SCHEMA + ". Create an SQL statement (without JOIN operations) to query the database for the information the user requests to read."    
                    queryMessages = [SystemMessage(queryInstructions),
                                     HumanMessage(prompt)]

                    # Get query response from LLM
                    response = llm.invoke(queryMessages)
                    print("Query Response:\n", response)
                    answer = response.content

                    # Extract SQL query from response
                    statement = extractQuery(response)
                    print("LLM's Query Statement: ", statement)

                    # Get result of SQL query
                    result = query_db(statement)
                    print("Query Result: ", result)

                    # If the query has an error, try fixing the query
                    fix_count = 0
                    while "Error" in str(result) and fix_count < MAX_FIX_ATTEMPTS:
                        fixPrompt = "The user prompted the following: " + prompt + ". In response, the following SQL query was generated: " + statement + ". However, it led to this " + str(result) + ". Return a corrected SQL query. If the query contains a JOIN operation, return a query based only on the trips table."
                        fixMessages = [SystemMessage(queryInstructions), HumanMessage(fixPrompt)]
                        response = llm.invoke(fixMessages)
                        #fixMessages.append(AIMessage(response.content))

                        statement = extractQuery(response)
                        result = query_db(statement)
                        #fixMessages.append(HumanMessage("The generated SQL gave me the following error: " + str(result) + ". Please generate a corrected query."))

                        print("Fix Attempt " + str(fix_count) + ":")
                        print("\tNew Query: ", statement)
                        print("\tNew Result: ", result)
                        fix_count += 1

                    if "Error" in str(result):
                        print("All attempts to fix the query have failed. Returning the error...")
                        answer = result

                    else:
                        if result:
                            # Configure the question prompt
                            systemInstructions = "You are a helpful assistant who only answers about King County Metro. The user's prompt can be answered with the following information: " + str(result) + ". The information was retrieved from the database using the following SQL query: " + statement + "."
                            systemMessages = [SystemMessage(systemInstructions), HumanMessage(prompt)]
                            
                            # Get question response
                            response = llm.invoke(systemMessages)
                            answer = response.content
                            print("Final Response:\n", response)
                        else:
                            answer = "I was not able to retrieve that information.\n\nQuery statement used:\n\n" + str(statement)

"""
