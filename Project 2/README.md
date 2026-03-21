# SC3020 Project 2 — Query Plan-Based SQL Comprehension

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git
- Python
---

## Project Structure

```
Project 2/
├── .env                        # Environment variables
├── .gitignore
├── Dockerfile                  # Builds the Python setup container
├── docker-compose.yml          # Orchestrates Postgres, setup, and pgAdmin
├── project.py                  # Entry Point
├── interface.py                # GUI, wires interface together for user
├── preprocessing.py            # DB Connection, QEP/AGP Fetching, Query Parsing
├── annotation.py               # Takes parsed QEP/AQP -> Generate Annotation Text
├── dummy_data.py               # Returns Hardcoded fake QEP/AQP data to enable parallel development
├── requirements.txt            # Python dependencies
│
├── pgadmin/
│   ├── servers.json            # Auto-registers Postgres server in pgAdmin
│   └── pgpass                  # Stores DB password for pgAdmin
│
├── data/                       # TPC-H CSV data files (not committed)
│   ├── region.csv
│   ├── nation.csv
│   ├── part.csv
│   ├── supplier.csv
│   ├── partsupp.csv
│   ├── customer.csv
│   ├── orders.csv
│   └── lineitem.csv
│
├── pgdata/                     # Postgres data volume (auto-created, not committed)
│
└── utils/
    └── setup_tpch.py           # Creates TPC-H schema and loads CSV data
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/MingKaiDev/SC3020-Group-20-AY25-S2.git
cd "Project 2"
```

### 2. Place TPC-H CSV data files

Put all 8 TPC-H `.csv` files into the `data/` folder:

```
data/region.csv
data/nation.csv
data/part.csv
data/supplier.csv
data/partsupp.csv
data/customer.csv
data/orders.csv
data/lineitem.csv
```

> The CSV files should use `|` as the delimiter with a trailing `|` at the end of
> each line (standard TPC-H dbgen output).

### 3. Start everything

```bash
docker compose up --build
```

This will:
1. Start a PostgreSQL 15 database
2. Run setup_tpch.py to create all TPC-H tables and load the CSV data
3. Start pgAdmin 4 for database management

---

## Accessing the Database

### pgAdmin (Browser UI)

Open http://localhost:5050 in your browser.

- Email: admin@admin.com
- Password: admin

The SC3020 server will already be registered and connected automatically.
If password is needed to verify - 1234

### psql (Command Line)

```bash
docker exec -it postgres psql -U postgres -d postgres
```

---

## Resetting the Database

To wipe all data and start fresh:

```bash
docker compose down

# Windows (PowerShell):
Remove-Item -Recurse -Force pgdata

# Mac/Linux:
rm -rf pgdata/

docker compose up --build
```

---

## Troubleshooting

| Problem                              | Fix                                              |
|--------------------------------------|--------------------------------------------------|
| setup container exits with code 1    | Check .env has DB_HOST=postgres                  |
| CSV files skipped                    | Ensure all 8 files are in data/ folder           |
| pgAdmin shows 401 errors             | Register server manually (Host: postgres, Port: 5432) |
| pgdata/ permission errors on Windows | Delete via File Explorer and rerun               |

---
