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
import re
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# SECTION 1: DATABASE CONNECTION
# =============================================================================

def get_connection(): #Done
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
    try:
        host = os.getenv("DB_HOST", "localhost")
        #host = "localhost"
        port = os.getenv("DB_PORT", "5432")
        dbname = os.getenv("DB_NAME", "postgres")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        conn = psycopg.connect(
            host=host, port=port,
            dbname=dbname, user=user,
            password=password,
            connect_timeout=5 
        )
        logger.info("Connected to PostgreSQL at %s:%s/%s", host, port, dbname)
        return conn
    except Exception as e:
        logger.exception("Failed to connect to PostgreSQL")
        raise ConnectionError(f"Failed to connect to PostgreSQL: {e}") from e

def close_connection(conn): #Done
    """
    Safely closes the database connection.

    Args:
        conn (psycopg.Connection): The connection to close.

    TODO:
        - Check if conn is not None before closing
        - Call conn.close()
    """
    if conn and not conn.closed:
        conn.close()
        logger.info("Database connection closed.")

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
    if not sql_query or not sql_query.strip():
        logger.warning("Query validation failed: empty or None query")
        return False

    cleaned = sql_query.strip()

    # Strip SQL comments to avoid false analysis
    no_comments = re.sub(r'--.*$', '', cleaned, flags=re.MULTILINE)
    no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
    no_comments = no_comments.strip()

    if not no_comments:
        logger.warning("Query validation failed: query contains only comments")
        return False

    # Strip string literals to avoid false positives on dangerous keywords
    no_strings = re.sub(r"'[^']*'", "''", no_comments)

    # Reject multiple statements
    statements = [s.strip() for s in no_strings.split(';') if s.strip()]
    if len(statements) > 1:
        logger.warning("Query validation failed: multiple statements detected")
        return False

    # Must start with SELECT or WITH
    first_word = no_comments.split()[0].upper()
    if first_word not in ('SELECT', 'WITH'):
        logger.warning("Query validation failed: must start with SELECT or WITH, got '%s'", first_word)
        return False

    # Reject dangerous keywords
    dangerous = re.search(
        r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b',
        no_strings, re.IGNORECASE
    )
    if dangerous:
        logger.warning("Query validation failed: dangerous keyword '%s'", dangerous.group())
        return False

    return True

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
    if not validate_query(sql_query):
        raise ValueError("Invalid SQL query — must be a read-only SELECT statement.")

    try:
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql_query}")
            result = cur.fetchone()[0]
        if isinstance(result, str):
            return json.loads(result)[0]
        elif isinstance(result, list):
            return result[0]
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to fetch QEP: {e}") from e
    finally:
        conn.rollback()


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
    if not validate_query(sql_query):
        raise ValueError("Invalid SQL query.")

    VALID_SETTINGS = {
        "enable_hashjoin", "enable_mergejoin", "enable_nestloop",
        "enable_seqscan", "enable_indexscan", "enable_indexonlyscan",
        "enable_bitmapscan", "enable_tidscan", "enable_sort",
        "enable_material", "enable_hashagg",
    }
    for op in disabled_operators:
        if op not in VALID_SETTINGS:
            raise ValueError(f"Invalid planner setting: {op}")

    try:
        with conn.cursor() as cur:
            for op in disabled_operators:
                cur.execute(f"SET LOCAL {op} = off")
            cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql_query}")
            result = cur.fetchone()[0]
        if isinstance(result, str):
            return json.loads(result)[0]
        elif isinstance(result, list):
            return result[0]
        return result
    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch AQP (disabled: {disabled_operators}): {e}"
        ) from e
    finally:
        conn.rollback()


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
    operator_groups = {
        "no_hashjoin":  ["enable_hashjoin"],
        "no_mergejoin": ["enable_mergejoin"],
        "no_nestloop":  ["enable_nestloop"],
        "no_seqscan":   ["enable_seqscan"],
        "no_indexscan": ["enable_indexscan"],
    }
    aqps = {}
    for label, operators in operator_groups.items():
        try:
            aqps[label] = get_aqp(conn, sql_query, operators)
        except Exception as e:
            logger.warning("AQP '%s' failed: %s", label, e)
            aqps[label] = None
    return aqps

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
    if nodes is None:
        nodes = []
    node = plan.get("Plan", plan)
    nodes.append(node)
    for child in node.get("Plans", []):
        parse_plan_nodes(child, nodes)
    return nodes


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
    return node.get("Total Cost", float("inf"))


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
    root = plan.get("Plan", plan)
    return get_node_cost(root)


# =============================================================================
# SECTION 6: ENTRY POINT (for quick testing) (disable when testing is over)
# =============================================================================

if __name__ == "__main__":
    conn = get_connection()
    try:
        print("=== Test 1: Simple scan ===")
        q1 = "SELECT * FROM nation"
        print(f"Validate: {validate_query(q1)}")
        qep = get_qep(conn, q1)
        print(f"QEP root: {qep['Plan']['Node Type']}, cost: {get_root_cost(qep)}")
        nodes = parse_plan_nodes(qep)
        print(f"Nodes: {len(nodes)}")
        aqps = get_all_aqps(conn, q1)
        print(f"AQP labels: {list(aqps.keys())}")
        for label, plan in aqps.items():
            cost = get_root_cost(plan) if plan else "N/A"
            print(f"  {label}: {cost}")

        print("\n=== Test 2: Join ===")
        q2 = "SELECT * FROM customer C, orders O WHERE C.c_custkey = O.o_custkey"
        qep2 = get_qep(conn, q2)
        print(f"QEP root: {qep2['Plan']['Node Type']}, cost: {get_root_cost(qep2)}")
        nodes2 = parse_plan_nodes(qep2)
        print(f"Nodes: {len(nodes2)}")
        for n in nodes2:
            print(f"  - {n['Node Type']} (cost: {get_node_cost(n)})")

        print("\n=== Test 3: Aggregate + sort ===")
        q3 = "SELECT c_nationkey, COUNT(*) FROM customer GROUP BY c_nationkey ORDER BY c_nationkey"
        qep3 = get_qep(conn, q3)
        print(f"QEP root: {qep3['Plan']['Node Type']}, cost: {get_root_cost(qep3)}")
        nodes3 = parse_plan_nodes(qep3)
        print(f"Nodes: {len(nodes3)}")
        for n in nodes3:
            print(f"  - {n['Node Type']} (cost: {get_node_cost(n)})")

        print("\n=== Validation tests ===")
        print(f"Empty: {validate_query('')}")
        print(f"None: {validate_query(None)}")
        print(f"DELETE: {validate_query('DELETE FROM nation')}")
        print(f"Multi-stmt: {validate_query('SELECT 1; DROP TABLE nation')}")

    finally:
        close_connection(conn)