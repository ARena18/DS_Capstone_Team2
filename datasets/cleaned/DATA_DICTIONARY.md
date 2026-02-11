# Data Dictionary - Transit Planning AI Assistant

**Project:** Transit Planning AI Assistant  
**Last Updated:** Feb 8th 2026 
**Data Source:** King County Metro  
**Purpose:** Documentation of all datasets used in the Transit Insights Assistant

---

## Table of Contents
1. [Overview](#overview)
2. [Dataset Summary](#dataset-summary)
3. [Trip-Level Data](#trip-level-data)
4. [Stop-Level Data](#stop-level-data)
6. [Reference Stop Data](#reference-data)

---

## Overview

### Purpose
This data dictionary documents all datasets, tables, columns, and data quality considerations for the Transit Planning AI Assistant project.

### Data Coverage
- **Geographic Coverage:** King County, Washington
- **Temporal Coverage:** 2025-01-01 to 2026-01-01
- **Update Frequency:** One-time snapshot
- **Total Records:** 2.925M trip records, 2.968 stop observations

### Key Entities
- **Routes:** 127 unique transit routes
- **Stops:** 6088 unique bus stops
- **Time Period:** 12 months/years of historical data

---

## Dataset Summary

| Dataset | File Name | Records | Date Range | Status |
|---------|-----------|---------|------------|--------|
| Trip-Level Data | `Trip_level_db.csv` | 2925275 | 2025-01-01 - 2025-12-31 | Loaded |
| Stop-Level Data | `Stop_level_db.csv` | 2968575 | 20205-01-02 - 2026-01-01 | Loaded |
| Stop Reference | `GIS_stop_cleaned.csv` | 490952 | N/A (Reference) |  Loaded |
| Route Reference | `routes_reference.csv` | [Number] | N/A (Reference) | Not Available |

**Legend:**
- Loaded - Data is loaded and validated
- In Progress - Data collection/loading in progress
- Not Available - Data not yet obtained

---

## Trip-Level Data

### Overview
Source of truth - Cleaned trip datset that represents individual transit trips/journeys taken by passengers by date

### File Information
- **Source File:** `Trip_level_db.csv`
- **File Size:** 353.5 MB
- **Total Records:** 2925275
- **Grain:** one row per (trip_id, operation_date)
- **Primary Key:** `trip_id, operation_date`

### Schema

| Column Name | Data Type | Description | Example Values | Null % | Notes |
|-------------|-----------|-------------|----------------|--------|-------|
| `trip_id` | BIGINT | Unique identifier for each trip per day | `73352704` | 0% | Primary key |
| `service_change_num` | String | Identified number of service change | `153` | 0% | Foreign key to service change |
| `service_rte_num` | String | Transit route identifier | `40`, `7`, `550` | 0% | Foreign key to routes |
| `operation_date` | Date | Date of the trip | `2025-01-15` | 0% | Format: YYYY-MM-DD, Primary key|
| `sched_start_time` | String | Time the trip scheduled to be started | `6:42:00 AM` | 0% | Format: HH:MM:SS, 24-hour |
| `actual_start_time` | String | Time the trip actually started | `06:42:45 AM` | 0% | Format: HH:MM:SS, 24-hour |
| `sched_end_time` | String | Time the trip scheduled to be ended | `6:54:00 AM` | 0% | Format: HH:MM:SS, 24-hour |
| `actual_end_time` | String | Time the trip actually ended | `06:55:09 AM` | 0% | Format: HH:MM:SS, 24-hour |
| `express_local_cd` | Category | Type of services: Express & Local | `E`, `L` | 0% | Local trips more than Express trips |
| `inbd_outbd_cd` | Category | Direction: Inbound & Outbound | `I`, `0` | 0% | Ratio not equal because some trips head to Base|
| `sched_day_type_coded_num` | Integer | Date type coded | `0`, `1`, `2`, `6` | 0% | 0-Weekday, 1-Saturday, 2-Sunday, 6-Holiday|
| `day_code` | Category | Type of operation date coded | `HOL`, `WK`, `SA`, `SU` | 0% | |
| `time_period` | Category | Time period in a day | `AM Peak`, `PM Peak`, `Evening` | 0% | |
| `psngr_boardings` | Decimal | Number of passenger on | `8.28`, `1.84`, `9.20` | 0% | Must >= 0 |
| `psngr_alightings` | Decimal | Number of passenger off | `0.0`, `1.84`, `2.4` | 0% | Must >= 0 |
| `max_psngr_load` | Decimal | Max number of passenger load at the same time  | `8`, `1`, `10` | 0% | Must >= 0 |
| `crowding_threshold_nbr` | Integer | Crowding threshold | `52`, `76` | 0% | Calculated based on vehicle type and capacity |

### Sample Data

```csv
TRIP_ID,SERVICE_CHANGE_NUM,SERVICE_RTE_NUM,OPERATION_DATE,SCHED_START_TIME,ACTUAL_START_TIME,SCHED_END_TIME,ACTUAL_END_TIME,EXPRESS_LOCAL_CD,INBD_OUTBD_CD,SCHED_DAY_TYPE_CODED_NUM,DAY_CODE,TIME_PERIOD,PSNGR_BOARDINGS,PSNGR_ALIGHTINGS,MAX_PSNGR_LOAD,CROWDING_THRESHOLD_NBR
73352704,243,1,2025-01-01,6:42:00 AM,06:42:45 AM,6:54:00 AM,06:55:09 AM,L,I,6,HOL,AM Peak,8.28,0.92,8.0,52
73352706,243,1,2025-01-01,8:42:00 AM,08:42:35 AM,8:54:00 AM,08:53:17 AM,L,I,6,HOL,AM Peak,9.2,0.92,9.0,52
73352653,243,1,2025-01-01,7:12:00 AM,07:13:31 AM,7:24:00 AM,07:29:21 AM,L,I,6,HOL,AM Peak,1.84,1.84,1.0,52
```

### Indexes
To support common analytical and planning queries on the trip-level dataset, the following indexes are implemented in the database. These indexes are designed to optimize filtering by date, route, and route-date combinations, which are frequent access patterns in transit performance analysis.

| Index Name | Index Columns | Index Type | Purpose/ Query optimizatiomn | 
|------------|---------------|------------|------------------------------|
| pk_trips | (trip_id, operation_date) | Primary Key (B-tree) | Uniqueness at the trip-day level and fast lookup of individual trips
| idx_trips_operation_date | (operation_date) | B-tree | Optimizes queries filter or aggregate trips by service date (e.g., daily trends, before/after analysis)
| idx_trips_route_date | (service_rte_num, operation_date) | B-tree | Optimizes route-level time-series queries, such as ridership or crowding trends by route over time
| idx_trips_route| (service_rte_num) | B-tree | Optimizes queries filtering or grouping by route across the full analysis period

### Data Quality Observations

**Missing Values:**
- `psngr_boarding` and `psngr_alightings`: 0.0002% missing from raw data - specific route 114 -> dropped

**Data Validation Rules:**
- `operation_date` must be between 2025-01-01 and 2025-12-31
- `psngr_boarding`, `psngr_alightings` and `MAX_PSNGR_LOAD` must be >= 0
- `actual_start_time` must be valid 24-hour time format
- No duplicate `trip_id` values

### Statistics

| Metric | Value |
|--------|-------|
| **Total Trips** | 2,925,259 |
| **Unique Routes** | 127 |
| **Date Range** |  2025-01-01 to 2025-12-31 |
| **Average Daily Trips** | 8,014 |
| **Total passenger boardings** | 73,847,230 |
| **Average boardings per trip** | 25.24 |
| **Total passenger alightings** | 73,906,740 |
| **Average alightings per trip** | 25.27 |
| **Average max load per trip** | 14.77 |
| **Total Deadheading Trips** | 28533 |

### Business Rules
- A trip represents a single journey from one stop to another
- `psngr_boardings` and `psngr_alightings` is collected using Automated Passenger Counter (APC)
- Multiple passengers can be on the same trip (e.g., family traveling together)

---

## Trip-Level Enriched View (trips_enriched)

### Overview
Analytical view derived from the trips base table that augments trip-level records with temporal and performance metrics computed at query time. This view is intended for analysis, reporting, and downstream AI-assisted querying, while preserving the base table as the system of record.

### File Info:
- **Base table:**  trips
- **Transformation layer:** PostgreSQL view
- **Grain:** One row per (trip_id, operation_date)

### Derived / Enriched Columns
| Column Name |Data type | Description | Example | Note | 
|-------------|----------|-------------|---------|---------------|
| `month` | Integer | Calendar month | 1 | Derived |
| `day_of_week` | Integer | Day of week (0–6) | 2 | Derived |
| `week_of_year`	| Integer | ISO week number | 1	| Derived |
| `is_weekend` | Boolean | Weekend indicator | false | Derived |
| `load_factor` | Numeric | MAX_PSNGR_LOAD / CROWDING_THRESHOLD_NBR | 0.15 | Derived |
| `is_crowded` | Boolean | Load exceeds crowding threshold | false | Derived |
| `load_category` | Category | Crowding severity classification | Low | Derived |

---

## Stop-Level Data

### Overview
Represents boarding and alighting activity aggregated by day at individual bus stops,.

### File Information
- **Source File:** `Stop_level_db.csv`
- **File Size:** 210.1 MB
- **Total Records:** 2,968,575
- **Grain:** One row per stop × route × operation_date
- **Primary Key:** `stop_id, operation_date, service_rte_list`

### Schema

| Column Name | Data Type | Description | Example Values | Null % | Notes |
|-------------|-----------|-------------|----------------|--------|-------|
| `operation_date` | Date | Date of observation | `2026-01-15` | 0% | Format: YYYY-MM-DD, Part of primary key |
| `stop_id` | String | Bus stop identifier | `12345` | 0% | Part of primary key |
| `stop_nm` | String | Human-readable stop name | `3rd Ave & Pine St` | 0% | Name can change |
| `service_rte_list` | String | Route serving this stop | `40`, `7`, `150` | 0% | Part of primary key |
| `sched_day_type_coded_num` | Integer | Date type coded | `0`, `1`, `2` | 0% | 0-Weekday, 1-Saturday, 2-Sunday |
| `day_code` | Category | Type of operation date coded | `WK`, `SA`, `SU` | 0% | |
| `day_name` | String | Name of Day in the week | `Monday`, `Tuesday`, `Friday` | 0% | Default 0 |
| `trips_count` | Integer | Number of trips | `8`, `17`, `22` | 0% | Default 0 |
| `total_boardings` | Integer | Total number of passengers boarding | `12`, `45`, `3` | 0% | Count of boardings |
| `total_alightings` | Integer | Total number of passengers alighting | `8`, `32`, `5` | 0% | Count of alightings |
| `avg_departure_load` | Decimal | Average of departure load | `8.2`, `3.7`, `5.0` | 0% |  |

### Sample Data

```csv
OPERATION_DATE,STOP_ID,STOP_NM,SERVICE_RTE_LIST,SCHED_DAY_TYPE_CODED_NUM,DAY_CODE,DAY_NAME,TRIPS_COUNT,TOTAL_BOARDINGS,TOTAL_ALIGHTINGS,AVG_DEPARTURE_LOAD
2025-01-02,25,BLANCHARD ST & 1ST AVE,678,0,WK,Thursday,2,0,0,0
2025-01-02,100,1ST AVE & SPRING ST,677,0,WK,Thursday,328,315,252,1
2025-01-02,101,SPRING ST & 3RD AVE,677,0,WK,Thursday,163,611,105,5
```

### Indexes
To support common analytical and planning queries on the trip-level dataset, the following indexes are implemented in the database.

| Index Name | Index Columns | Index Type | Purpose/ Query optimizatiomn | 
|------------|---------------|------------|------------------------------|
| pk_stop_daily |	(stop_id, operation_date, service_rte_list) | Primary Key (B-tree) | Uniqueness at stop×route×date grain & supports key-based lookups|
| idx_stop_daily_date |	(stop_id, operation_date)	| B-tree	| Optimizes stop-level time filtering (e.g., one stop over a date range) |
| idx_stop_daily_stop | (stop_id) |	B-tree | Optimizes queries filtering/grouping by stop_id |

### Data Quality Observations

**Missing Values:**
- 0 missing

**Data Validation Rules:**
- `total_boardings`, `total_alightings` and `avg_departure_load` must be >= 0
- `observation_date` must be valid date between 2025-01-02 and 2026-01-01
- Total daily boardings should roughly equal total daily alightings (system-wide)

### Statistics

| Metric | Value |
|--------|-------|
| **Total Observations** | 2968575 |
| **Unique Stops** | 6088 |
| **Total unique routes:** | 146
| **Date Range** | 2025-01-02 to 2026-01-01 |
| **Average Boardings per Stop (across period)** | 15,864.50 |
| **Busiest Stop** | 3rd Ave & Pike St (~900,000 daily boardings) |
| **Total Boardings** | 96,583,051 |
| **Total Alightings** | 96,585,495 |
| **Average boardings per stop:** | 32.54 |
| **Average alightings per stop:** | 32.54 |

### Business Rules
- Boardings represent passengers getting ON the bus
- Alightings represent passengers getting OFF the bus
- A stop can serve multiple routes
- Data is typically aggregated by hour for privacy and storage efficiency
- Some stops may have zero activity during certain hours (late night, early morning)

---

## Stop-Level Enriched View (stop_enriched)

### Overview
Analytical view derived from the stop_daily base table. It adds temporal features and per-trip ridership metrics computed at query time, while keeping stop_daily as the system-of-record.

### Source
- **Base table:** public.stop_daily
- **Transformation layer:** PostgreSQL view (CREATE OR REPLACE VIEW)
- **Grain:** One row per (stop_id, operation_date, service_rte_list)
(same as stop_daily, because the view is sd.* plus calculated fields)

### Derived / Enriched Columns
| Column Name |Data type | Description | Example | Note | 
|-------------|----------|-------------|---------|---------------|
| `month` | SMALLINT | Month extracted from operation_date | 1, 12 | 0% | EXTRACT(MONTH FROM operation_date)
| `week` | SMALLINT	| Week number extracted from operation_date | 1, 35, 53 | 0% | EXTRACT(WEEK FROM operation_date) (PostgreSQL week-of-year; not ISO week-year)
| `day_of_week` | SMALLINT | Day of week (0–6) extracted from operation_date | 0, 1, 6 | 0%	| EXTRACT(DOW...) → 0=Sunday, 1=Monday, …, 6=Saturday
| `is_weekend` | BOOLEAN | Weekend indicator derived from day_of_week | true, false | 0%	| TRUE if `day_of_week` IN (0,6) else FALSE
| `boardings_per_trip` | Numeric | Average boardings per trip for that stop-route-day | `0.96036`, `0.0` | 0% | Calculated by dividing TOTAL_BOARDINGS to TRIPS_COUNT  |
| `alightings_per_trip` | Numeric | Average alightings per trip for that stop-route-day | `0.96036`, `0.0` | 0% | Calculated by dividing TOTAL_ALIGHTINGS to TRIPS_COUNT  |
| `net_passenger` | Integer | Differences between alightings and boardings | `0.96036`, `0.0` | 0% | Calculated by subtracting TOTAL_ALIGHTINGS to TOTAL_BOARDINGS  |

 ---

## GIS Transit Stops Reference Table

### Overview
Versioned stop dimension table containing geographic and effective-date metadata for transit stops.
Supports temporal joins to fact tables (e.g., stop_daily) to ensure correct stop attributes are used for a given operation date.

### File Information
- **Total records:** 490,952 rows
- **Grain:** One row per stop_id × eff_start_date (versioned stop record)
- **Primary Key:** `stop_id, eff_start_date`

### Schema

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `stop_id` | String | Unique stop identifier | `12345` |
| `eff_start_date` | datetime | Effective start date of the stop | `2024-09-15` |
| `eff_end_date` | datetime | Effective end date of the stop | `2025-12-15` |
| `on_street_nm` | String | Official stop name | `3rd Ave & Pine St` |
| `gps_latitude` | Numeric | Latitude coordinate | `47.6097` |
| `gps_longitude` | Numeric | Longitude coordinate | `-122.3331` |
| `gis_zip_cd` | String | Geographic zone/area zip code | `98801`, `98109` |
| `change_num` | Integer | Number of service change for stop | `157`, `159` |
| `gis_regional_fare_zone` | VARCHAR(10) | Fare zone classification | `24`, `36` | 

### Constraints
- eff_end_date must be NULL or ≥ eff_start_date
- gps_latitude must be between -90 and 90
- gps_longitude must be between -180 and 180

### Indexes
| Index Name | Index Columns | Purpose/ Query optimizatiomn | 
|------------|---------------|------------------------------|
| pk_stops_reference |	(stop_id, eff_start_date) | Enforces versioned uniqueness | 
| idx_stops_ref_lookup | (stop_id, eff_start_date, eff_end_date) | Optimizes temporal joins to fact tables |
| idx_stops_ref_zip | (gis_zip_cd) | Optimizes geographic filtering |

**Usage:** Geographic analysis, mapping, accessibility features

### Known Limitations
- Does not enforce non-overlapping effective date ranges for the same stop_id
- Does not include vehicle platform attributes
- Latitude/longitude precision limited to 7 decimal places

---

## Data Lineage

### Data Flow

```
King County Metro Systems
          ↓
Raw CSV Exports (provided by contact)
          ↓
Data Exploration & Profiling (Jupyter notebook)
          ↓
Data Cleaning & Transformation (etl.py)
          ↓
PostgreSQL Database (transit.db)
          ↓
Query Functions (query_functions.py)
          ↓
LLM / UI Layer
```

### Data Refresh
- **Frequency:** One-time snapshot
- **Last Update:** Feb 8th 2026
- **Next Refresh:** Not scheduled - static dataset

### Data Transformations

**Trip Data Transformations:**
1. Parse dates to YYYY-MM-DD
2. Create combined trip_datetime from separate date/time fields
3. Dropped 16 rows of missing PSNGR_BOARDINGS and PSNGR_ALIGHTINGS

**Stop Data Transformations:**
1. Parse dates to YYYY-MM-DD
2. Ensure boardings/alightings are non-negative

---

## Change Log

| Date | Changed By | Changes Made | Reason |
|------|------------|--------------|--------|
| 2026-01-26 | Quyen | Initial data dictionary created | Project kickoff |
| 2026-01-28 | Quyen | Added trip-level statistics | After data loading |
| 2026-02-08 | Quyen | Added stop-level statistics | After data loading |
| 2026-02-08 | Quyen | Updated data quality notes | After cleaning |

---

## Contact Information

**Data Owner:** Quyen Bui  
**Email:** qbui@seattleu.edu
**Project Repository:** (https://github.com/ARena18/DS_Capstone_Team2.git) 

**Questions or Issues:**
- For data quality issues, contact Quyen Bui
- For source data questions, contact King County Metro
- For schema questions, see project documentation

---


