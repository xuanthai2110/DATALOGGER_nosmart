# Datalogger Solar Monitoring System

## 1. Project Overview

The **Solar Datalogger System** is a local data acquisition and
monitoring platform designed to collect operational data from multiple
solar inverters, process and normalize the data, store historical
information, and provide both **local real‑time monitoring** and **cloud
reporting**.

The system acts as an intermediary between solar inverters deployed at a
plant and a central cloud monitoring server. It ensures reliable data
acquisition, efficient storage, and responsive local visualization for
technicians and operators.

This system is typically deployed on an **industrial computer, edge
gateway, or Raspberry Pi** located inside the solar plant network.

Main goals of the system:

-   Collect data from multiple inverters via communication protocols
    (e.g., Modbus RTU / TCP)
-   Normalize and standardize telemetry data
-   Store historical production data locally
-   Provide a **local web dashboard for real‑time monitoring**
-   Periodically upload summarized data to a **central cloud server**
-   Provide configuration tools for plant setup

------------------------------------------------------------------------

# 2. System Architecture

The system is divided into several main modules:

1.  Data Acquisition Layer
2.  Data Processing & Normalization
3.  Realtime Data Cache
4.  Local Database Storage
5.  Cloud Communication Service
6.  Local Web Monitoring Interface
7.  System Services and Infrastructure

Overall data flow:

Inverter → Data Reader → Parser → Normalizer → Realtime Cache\
→ Local Web Dashboard\
→ Database Storage (periodic)\
→ Cloud Upload Service

------------------------------------------------------------------------

# 3. Main Functional Modules

## 3.1 Inverter Data Acquisition

The datalogger communicates with solar inverters through supported
communication protocols such as:

-   Modbus RTU
-   Modbus TCP
-   RS485 communication

Responsibilities:

-   Periodically read inverter registers (e.g., every 30 seconds)
-   Support multiple inverter brands and models
-   Manage communication scheduling
-   Handle communication errors and reconnection

Collected parameters may include:

-   DC Voltage / Current
-   AC Voltage / Current
-   Active Power
-   Daily Energy
-   Total Energy
-   Inverter Status
-   Temperature
-   MPPT data
-   String current

------------------------------------------------------------------------

## 3.2 Data Parsing and Normalization

Raw register values from inverters must be decoded and converted into
standardized telemetry data.

Responsibilities:

-   Decode register values
-   Convert signed / unsigned values
-   Apply scaling factors
-   Convert raw protocol values into engineering units

Example normalized parameters:

-   Power (kW)
-   Voltage (V)
-   Current (A)
-   Energy (kWh)
-   Temperature (°C)

This allows the system to support **multiple inverter brands with a
unified data model**.

------------------------------------------------------------------------

## 3.3 Realtime Data Cache

Realtime data is stored temporarily in **RAM memory**.

Purpose:

-   Provide fast access for the local web dashboard
-   Avoid frequent database queries
-   Reduce disk I/O

Features:

-   Stores the most recent telemetry for each inverter
-   Updated every data acquisition cycle
-   Used by the local web interface for realtime display

------------------------------------------------------------------------

## 3.4 Local Database Storage

The system stores historical telemetry data in a **local database**.

Recommended database:

-   SQLite

Storage strategy:

-   Data acquisition every **30 seconds**
-   Database storage every **5 minutes**

Benefits:

-   Reduces database size
-   Improves system performance
-   Maintains sufficient historical resolution

------------------------------------------------------------------------

## 3.5 Cloud Upload Service

The datalogger periodically sends plant data to a **central monitoring
server**.

Upload interval:

-   Every **5 minutes**

Responsibilities:

-   Aggregate data from the local database
-   Format data into API payloads
-   Send data via HTTP/HTTPS REST API
-   Handle network failures and retries

------------------------------------------------------------------------

## 3.6 Local Web Monitoring Interface

The system includes a **local web dashboard** accessible through the
plant network.

Main features:

### Dashboard

Displays:

-   Total plant power
-   Daily energy production
-   Total lifetime energy
-   Inverter status
-   Alarm status

### Inverter Monitoring

Displays realtime information for each inverter.

### MPPT Monitoring

Shows MPPT voltage and current values.

### String Monitoring

Displays individual string current values.

### Configuration Interface

Allows configuration of:

-   Project information
-   Inverter settings
-   Communication parameters
-   Network configuration

------------------------------------------------------------------------

# 4. System Folder Structure

The project is organized into several major directories:

-   core/ → Data acquisition, processing, database, cloud upload
-   web_local/ → Local web backend and frontend
-   prompts/ → Development documentation and prompt files
-   devops/ → Docker, environment, requirements, scripts
-   data/ → Database files and logs

------------------------------------------------------------------------

# 5. Key Features

-   Multi‑inverter support
-   Realtime local monitoring
-   Efficient historical data storage
-   Cloud synchronization
-   Modular architecture
-   Scalable system design

------------------------------------------------------------------------

# 6. Typical Operation Timing

  Task                    Interval
  ----------------------- ---------------
  Inverter Data Reading   30 seconds
  Realtime Web Update     5--30 seconds
  Database Storage        5 minutes
  Cloud Data Upload       5 minutes

------------------------------------------------------------------------

# 7. Deployment Environment

The system can run on:

-   Industrial edge computers
-   Linux gateways
-   Raspberry Pi
-   Embedded datalogger devices

Recommended environment:

-   Linux OS
-   Python runtime
-   Docker (optional)

------------------------------------------------------------------------

# 8. Conclusion

The Solar Datalogger System provides a reliable edge computing solution
for solar plants. It combines data acquisition, realtime monitoring,
historical storage, and cloud integration to support efficient operation
and maintenance of photovoltaic systems.
