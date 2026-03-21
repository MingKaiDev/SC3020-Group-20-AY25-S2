# preprocessing.py
# Responsibilities:
#   - Establish and manage PostgreSQL database connection
#   - Accept and validate SQL query input
#   - Fetch the Query Execution Plan (QEP) from PostgreSQL
#   - Fetch Alternative Query Plans (AQPs) by toggling planner settings
#   - Parse and flatten QEP/AQP plan trees into usable structures
#   - Pass processed data to annotation.py

import psycopg
import os
import json
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# SECTION 1: DATABASE CONNECTION
# =============================================================================

def get_connection():
    """
    Establishes and returns a connection to the PostgreSQL database.
    Reads credentials from the .env file.

    Returns:
        psycopg.Connection: A live database connection object.

    TODO:
        - Load DB credentials from .env using os.getenv()
        - Call psycopg.connect() with host, port, dbname, user, password
        - Raise a clear error message if connection fails
    """
    return psycopg.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def close_connection(conn):
    """
    Safely closes the database connection.

    Args:
        conn (psycopg.Connection): The connection to close.

    TODO:
        - Check if conn is not None before closing
        - Call conn.close()
    """
    pass

# =============================================================================
# SECTION 2: QUERY VALIDATION
# =============================================================================

def validate_query(sql_query: str) -> bool:
    """
    Performs basic validation on the input SQL query string.

    Args:
        sql_query (str): The raw SQL query string from user/GUI input.

    Returns:
        bool: True if valid, False otherwise.

    TODO:
        - Check that the query is not None or empty string
        - Check it starts with a valid SQL keyword (SELECT, WITH, etc.)
        - Optionally: check for SQL injection patterns to sanitize input
        - Return False with a descriptive print/log message if invalid
    """
    pass

# =============================================================================
# SECTION 3: FETCH QUERY EXECUTION PLAN (QEP)
# =============================================================================

def get_qep(conn, sql_query: str) -> dict:
    """
    Fetches the Query Execution Plan (QEP) chosen by PostgreSQL's optimizer.
    Uses EXPLAIN (ANALYZE, FORMAT JSON) to retrieve the plan with cost estimates.

    Args:
        conn (psycopg.Connection): Active database connection.
        sql_query (str): A validated SQL query string.

    Returns:
        dict: The root node of the QEP as a parsed Python dictionary.

    TODO:
        - Open a cursor using conn.cursor()
        - Execute: EXPLAIN (ANALYZE, FORMAT JSON) <sql_query>
        - Fetch the result with cur.fetchone()
        - Return result[0][0] — this is the parsed JSON plan dict
        - Handle exceptions (e.g. invalid SQL syntax) and raise with a clear message

    NOTE:
        The returned dict has structure: { "Plan": { "Node Type": ..., "Plans": [...] } }
    """
    pass


# =============================================================================
# SECTION 4: FETCH ALTERNATIVE QUERY PLANS (AQPs)
# =============================================================================

def get_aqp(conn, sql_query: str, disabled_operators: list) -> dict:
    """
    Fetches a single Alternative Query Plan (AQP) by disabling specific
    PostgreSQL planner operators, forcing the optimizer to choose differently.

    Args:
        conn (psycopg.Connection): Active database connection.
        sql_query (str): A validated SQL query string.
        disabled_operators (list): List of planner settings to disable.
                                   e.g. ["enable_hashjoin", "enable_seqscan"]

    Returns:
        dict: The root node of the AQP as a parsed Python dictionary.

    TODO:
        - Open a cursor
        - For each operator in disabled_operators, run: SET <operator> = off
        - Run EXPLAIN (ANALYZE, FORMAT JSON) <sql_query> and fetch result
        - Re-enable all operators afterwards: SET <operator> = on
        - Return the plan dict (same structure as get_qep)
        - Wrap in try/except — some AQPs may be impossible (e.g. no index exists)

    REFERENCE:
        PostgreSQL planner settings:
        https://www.postgresql.org/docs/9.2/runtime-config-query.html
    """
    pass


def get_all_aqps(conn, sql_query: str) -> dict:
    """
    Collects multiple AQPs by disabling different operator groups one at a time.
    This gives annotation.py enough data to compare costs across plan alternatives.

    Args:
        conn (psycopg.Connection): Active database connection.
        sql_query (str): A validated SQL query string.

    Returns:
        dict: A mapping of plan label → AQP plan dict.
              e.g. { "no_hashjoin": {...}, "no_seqscan": {...}, ... }

    TODO:
        - Define a dict of operator groups to disable, for example:
            {
                "no_hashjoin":  ["enable_hashjoin"],
                "no_mergejoin": ["enable_mergejoin"],
                "no_nestloop":  ["enable_nestloop"],
                "no_seqscan":   ["enable_seqscan"],
                "no_indexscan": ["enable_indexscan"],
            }
        - Loop through each group and call get_aqp()
        - Store results in a dict with the label as key
        - If get_aqp() raises an exception, store None for that label
    """
    pass

# =============================================================================
# SECTION 5: PLAN TREE PARSING
# =============================================================================

def parse_plan_nodes(plan: dict, nodes=None) -> list:
    """
    Recursively walks the QEP/AQP plan tree and returns a flat list of all nodes.
    This makes it easy for annotation.py to scan for specific operator types.

    Args:
        plan (dict): The root plan dict (output of get_qep or get_aqp).
        nodes (list): Accumulator list — leave as None on first call.

    Returns:
        list: A flat list of all node dicts in the plan tree.

    TODO:
        - Handle both "Plan" wrapper (from root) and raw node dicts (from recursion)
        - Append current node to nodes list
        - Recurse into node.get("Plans", []) for child nodes
        - Return the completed nodes list

    EXAMPLE OUTPUT:
        [
          { "Node Type": "Hash Join", "Total Cost": 4523.0, ... },
          { "Node Type": "Seq Scan",  "Relation Name": "orders", ... },
          { "Node Type": "Hash",      ... },
          { "Node Type": "Seq Scan",  "Relation Name": "customer", ... }
        ]
    """
    pass


def get_node_cost(node: dict) -> float:
    """
    Safely extracts the total cost estimate from a single plan node.

    Args:
        node (dict): A single plan node dict.

    Returns:
        float: The "Total Cost" value, or infinity if not found.

    TODO:
        - Return node.get("Total Cost", float("inf"))
    """
    pass


def get_root_cost(plan: dict) -> float:
    """
    Extracts the total cost from the root node of a full plan dict.
    Used by annotation.py to compare QEP cost vs AQP costs.

    Args:
        plan (dict): Full plan dict (output of get_qep or get_aqp).

    Returns:
        float: The total cost at the root node.

    TODO:
        - Access the root node via plan.get("Plan", plan)
        - Call get_node_cost() on it and return the result
    """
    pass


# =============================================================================
# SECTION 6: ENTRY POINT (for quick testing) (disable when testing is over)
# =============================================================================

if __name__ == "__main__":
    # Quick test to verify preprocessing works end-to-end
    # TODO (for testing only):
    #   1. Call get_connection() and print "Connected successfully"
    #   2. Define a simple test query e.g.:
    #      "SELECT * FROM customer C, orders O WHERE C.c_custkey = O.o_custkey"
    #   3. Call validate_query() on it
    #   4. Call get_qep() and print the Node Type of the root plan node
    #   5. Call get_all_aqps() and print the keys of the returned dict
    #   6. Call parse_plan_nodes() and print how many nodes were found
    #   7. Call close_connection()
    pass