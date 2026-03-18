# setup_tpch.py
# Creates all TPC-H tables in PostgreSQL and optionally loads .csv data files.
# Uses same connection pattern as Task14.py (psycopg + dotenv)

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

# --- 1. Open connection ---
conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

# --- 2. DDL Statements for all TPC-H tables (in dependency order) ---
CREATE_STATEMENTS = [
    # Region (no FK dependencies)
    """
    CREATE TABLE IF NOT EXISTS public.region (
        r_regionkey integer NOT NULL,
        r_name      character(25)        NOT NULL,
        r_comment   character varying(152),
        CONSTRAINT region_pkey PRIMARY KEY (r_regionkey)
    ) TABLESPACE pg_default;
    ALTER TABLE public.region OWNER TO postgres;
    """,

    # Nation (depends on region)
    """
    CREATE TABLE IF NOT EXISTS public.nation (
        n_nationkey integer NOT NULL,
        n_name      character(25)         NOT NULL,
        n_regionkey integer               NOT NULL,
        n_comment   character varying(152),
        CONSTRAINT nation_pkey PRIMARY KEY (n_nationkey),
        CONSTRAINT fk_nation FOREIGN KEY (n_regionkey)
            REFERENCES public.region (r_regionkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION
    ) TABLESPACE pg_default;
    ALTER TABLE public.nation OWNER TO postgres;
    """,

    # Part (no FK dependencies)
    """
    CREATE TABLE IF NOT EXISTS public.part (
        p_partkey     integer              NOT NULL,
        p_name        character varying(55) NOT NULL,
        p_mfgr        character(25)         NOT NULL,
        p_brand       character(10)         NOT NULL,
        p_type        character varying(25) NOT NULL,
        p_size        integer               NOT NULL,
        p_container   character(10)         NOT NULL,
        p_retailprice numeric(15,2)         NOT NULL,
        p_comment     character varying(23) NOT NULL,
        CONSTRAINT part_pkey PRIMARY KEY (p_partkey)
    ) TABLESPACE pg_default;
    ALTER TABLE public.part OWNER TO postgres;
    """,

    # Supplier (depends on nation)
    """
    CREATE TABLE IF NOT EXISTS public.supplier (
        s_suppkey   integer               NOT NULL,
        s_name      character(25)         NOT NULL,
        s_address   character varying(40) NOT NULL,
        s_nationkey integer               NOT NULL,
        s_phone     character(15)         NOT NULL,
        s_acctbal   numeric(15,2)         NOT NULL,
        s_comment   character varying(101) NOT NULL,
        CONSTRAINT supplier_pkey PRIMARY KEY (s_suppkey),
        CONSTRAINT fk_supplier FOREIGN KEY (s_nationkey)
            REFERENCES public.nation (n_nationkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION
    ) TABLESPACE pg_default;
    ALTER TABLE public.supplier OWNER TO postgres;
    """,

    # Partsupp (depends on part, supplier)
    """
    CREATE TABLE IF NOT EXISTS public.partsupp (
        ps_partkey   integer               NOT NULL,
        ps_suppkey   integer               NOT NULL,
        ps_availqty  integer               NOT NULL,
        ps_supplycost numeric(15,2)        NOT NULL,
        ps_comment   character varying(199) NOT NULL,
        CONSTRAINT partsupp_pkey PRIMARY KEY (ps_partkey, ps_suppkey),
        CONSTRAINT fk_ps_partkey FOREIGN KEY (ps_partkey)
            REFERENCES public.part (p_partkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION,
        CONSTRAINT fk_ps_suppkey FOREIGN KEY (ps_suppkey)
            REFERENCES public.supplier (s_suppkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION
    ) TABLESPACE pg_default;
    ALTER TABLE public.partsupp OWNER TO postgres;
    """,

    # Customer (depends on nation)
    """
    CREATE TABLE IF NOT EXISTS public.customer (
        c_custkey   integer               NOT NULL,
        c_name      character varying(25) NOT NULL,
        c_address   character varying(40) NOT NULL,
        c_nationkey integer               NOT NULL,
        c_phone     character(15)         NOT NULL,
        c_acctbal   numeric(15,2)         NOT NULL,
        c_mktsegment character(10)        NOT NULL,
        c_comment   character varying(117) NOT NULL,
        CONSTRAINT customer_pkey PRIMARY KEY (c_custkey),
        CONSTRAINT fk_customer FOREIGN KEY (c_nationkey)
            REFERENCES public.nation (n_nationkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION
    ) TABLESPACE pg_default;
    ALTER TABLE public.customer OWNER TO postgres;
    """,

    # Orders (depends on customer)
    """
    CREATE TABLE IF NOT EXISTS public.orders (
        o_orderkey      integer               NOT NULL,
        o_custkey       integer               NOT NULL,
        o_orderstatus   character(1)          NOT NULL,
        o_totalprice    numeric(15,2)         NOT NULL,
        o_orderdate     date                  NOT NULL,
        o_orderpriority character(15)         NOT NULL,
        o_clerk         character(15)         NOT NULL,
        o_shippriority  integer               NOT NULL,
        o_comment       character varying(79) NOT NULL,
        CONSTRAINT orders_pkey PRIMARY KEY (o_orderkey),
        CONSTRAINT fk_orders_custkey FOREIGN KEY (o_custkey)
            REFERENCES public.customer (c_custkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION
    ) TABLESPACE pg_default;
    ALTER TABLE public.orders OWNER TO postgres;
    """,

    # Lineitem (depends on orders, part, supplier)
    """
    CREATE TABLE IF NOT EXISTS public.lineitem (
        l_orderkey      integer               NOT NULL,
        l_partkey       integer               NOT NULL,
        l_suppkey       integer               NOT NULL,
        l_linenumber    integer               NOT NULL,
        l_quantity      numeric(15,2)         NOT NULL,
        l_extendedprice numeric(15,2)         NOT NULL,
        l_discount      numeric(15,2)         NOT NULL,
        l_tax           numeric(15,2)         NOT NULL,
        l_returnflag    character(1)          NOT NULL,
        l_linestatus    character(1)          NOT NULL,
        l_shipdate      date                  NOT NULL,
        l_commitdate    date                  NOT NULL,
        l_receiptdate   date                  NOT NULL,
        l_shipinstruct  character(25)         NOT NULL,
        l_shipmode      character(10)         NOT NULL,
        l_comment       character varying(44) NOT NULL,
        CONSTRAINT lineitem_pkey PRIMARY KEY (l_orderkey, l_partkey, l_suppkey, l_linenumber),
        CONSTRAINT fk_lineitem_orderkey FOREIGN KEY (l_orderkey)
            REFERENCES public.orders (o_orderkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION,
        CONSTRAINT fk_lineitem_partkey FOREIGN KEY (l_partkey)
            REFERENCES public.part (p_partkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION,
        CONSTRAINT fk_lineitem_suppkey FOREIGN KEY (l_suppkey)
            REFERENCES public.supplier (s_suppkey)
            ON UPDATE NO ACTION ON DELETE NO ACTION
    ) TABLESPACE pg_default;
    ALTER TABLE public.lineitem OWNER TO postgres;
    """
]

# --- 3. Table-to-CSV mapping for bulk loading (set CSV_DIR to your folder) ---
CSV_DIR = r"C:\path\to\your\tpch\csv"   # <-- CHANGE THIS

TABLE_CSV_MAP = {
    "region":   "region.csv",
    "nation":   "nation.csv",
    "part":     "part.csv",
    "supplier": "supplier.csv",
    "partsupp": "partsupp.csv",
    "customer": "customer.csv",
    "orders":   "orders.csv",
    "lineitem": "lineitem.csv",
}

# --- 4. Execute DDL and load data ---
with conn.cursor() as cur:
    try:
        # Create tables
        for stmt in CREATE_STATEMENTS:
            cur.execute(stmt)
        print("All TPC-H tables created successfully.")

        # Load CSV data using COPY (fastest bulk load method)
        for table, csv_file in TABLE_CSV_MAP.items():
            csv_path = os.path.join(CSV_DIR, csv_file)
            if os.path.exists(csv_path):
                with open(csv_path, "r") as f:
                    with cur.copy(f"COPY public.{table} FROM STDIN WITH (FORMAT CSV, DELIMITER ',')") as copy:
                        while data := f.read(8192):
                            copy.write(data)
                print(f"  Loaded: {table}")
            else:
                print(f"  Skipped (file not found): {csv_path}")

        conn.commit()
        print("All data loaded and committed.")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")

# --- 5. Close connection ---
conn.close()
