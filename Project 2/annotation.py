# annotation.py
# Responsibilities:
#   - Receive parsed QEP and AQPs from preprocessing.py
#   - Identify operators used in the QEP (scans, joins, aggregations, sorts, etc.)
#   - Compare QEP costs against AQP costs to explain WHY operators were chosen
#   - Generate human-readable annotation strings for each SQL clause/component
#   - Return a structured annotation result to interface.py

from preprocessing import parse_plan_nodes, get_root_cost, get_node_cost

from dummy_data import get_dummy_qep, get_dummy_aqps 
# =============================================================================
# SECTION 1: CONSTANTS
# =============================================================================

# Node type categories — extend these if you encounter new operator types
SCAN_NODES  = {"Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan",
               "Bitmap Index Scan", "Tid Scan"}

JOIN_NODES  = {"Hash Join", "Merge Join", "Nested Loop"}

OTHER_NODES = {"Aggregate", "Hash Aggregate", "Group Aggregate",
               "Sort", "Limit", "Unique", "Hash", "Materialize",
               "Gather", "Gather Merge", "Subquery Scan"}

# AQP label → human-readable alternative name (used in annotation messages)
AQP_LABEL_MAP = {
    "no_hashjoin":  "Hash Join",
    "no_mergejoin": "Merge Join",
    "no_nestloop":  "Nested Loop",
    "no_seqscan":   "Sequential Scan",
    "no_indexscan": "Index Scan",
}

# =============================================================================
# SECTION 2: COST COMPARISON HELPERS
# =============================================================================

def compare_costs(qep_cost: float, aqp_cost: float) -> float:
    """
    Computes how many times more expensive an AQP is compared to the QEP.

    Args:
        qep_cost (float): Total cost of the chosen QEP.
        aqp_cost (float): Total cost of an alternative plan (AQP).

    Returns:
        float: The cost ratio (aqp_cost / qep_cost), rounded to 1 decimal.
               Returns 0.0 if qep_cost is zero to avoid division by zero.

    TODO:
        - Guard against qep_cost == 0
        - Return round(aqp_cost / qep_cost, 1)
    """
    pass


def get_cost_comparison_reasons(qep_cost: float, aqps: dict,
                                 skip_label: str = None) -> list:
    """
    Compares the QEP cost against all available AQPs and returns a list
    of reason strings explaining why alternatives were more expensive.

    Args:
        qep_cost (float): Total cost of the QEP root node.
        aqps (dict): Dict of label → AQP plan (from get_all_aqps).
        skip_label (str): Optional AQP label to skip (e.g. skip "no_hashjoin"
                          when annotating a Hash Join — don't compare against itself).

    Returns:
        list[str]: Reason strings e.g. ["Merge Join costs ~7.2x more",
                                         "Nested Loop costs ~10.4x more"]

    TODO:
        - Loop through aqps.items()
        - Skip if label == skip_label or if plan is None
        - Call get_root_cost() on the AQP plan
        - Call compare_costs() to get the ratio
        - Only add a reason if ratio > 1.0 (AQP is more expensive)
        - Format reason as: "<AQP_LABEL_MAP[label]> costs ~<ratio>x more"
    """
    pass

# =============================================================================
# SECTION 3: SCAN ANNOTATION
# =============================================================================

def annotate_scans(qep_nodes: list) -> list:
    """
    Generates annotation strings for all scan operations found in the QEP.
    Explains what scan type was used and why (e.g. no index → seq scan).

    Args:
        qep_nodes (list): Flat list of all QEP nodes (from parse_plan_nodes).

    Returns:
        list[str]: One annotation string per scan node found.

    TODO:
        - Filter nodes where node["Node Type"] is in SCAN_NODES
        - For each scan node, extract:
            - "Relation Name" → the table being scanned
            - "Node Type"     → the scan operator used
            - "Index Name"    → only present for Index Scan / Index Only Scan
            - "Filter"        → only present if a WHERE filter was applied
        - Write a different annotation message per scan type:
            * Seq Scan:
                "Table '<table>' is read using Sequential Scan.
                 This is likely because no usable index exists on the filtered columns."
            * Index Scan / Index Only Scan:
                "Table '<table>' is accessed via Index Scan on '<index_name>'.
                 An index was available and used to avoid a full table scan."
            * Bitmap Heap Scan:
                "Table '<table>' is accessed via Bitmap Heap Scan.
                 This handles multiple matching rows efficiently using a bitmap."
            * Default fallback:
                "Table '<table>' is accessed using <node_type>."
        - Append filter info if "Filter" key exists:
            " Filter applied: <filter>"
    """
    pass

# =============================================================================
# SECTION 4: JOIN ANNOTATION
# =============================================================================

def annotate_joins(qep_nodes: list, aqps: dict, qep_cost: float) -> list:
    """
    Generates annotation strings for all join operations found in the QEP.
    Uses AQP cost comparisons to explain WHY the chosen join was selected.

    Args:
        qep_nodes (list): Flat list of all QEP nodes (from parse_plan_nodes).
        aqps (dict): Dict of label → AQP plan (from get_all_aqps).
        qep_cost (float): Total cost of the QEP root (from get_root_cost).

    Returns:
        list[str]: One annotation string per join node found.

    TODO:
        - Filter nodes where node["Node Type"] is in JOIN_NODES
        - For each join node, extract:
            - "Node Type"       → join operator (Hash Join, Merge Join, Nested Loop)
            - "Join Type"       → e.g. Inner, Left, Semi
            - "Hash Cond"       → present for Hash Join (the join condition)
            - "Merge Cond"      → present for Merge Join
            - "Join Filter"     → present for Nested Loop
        - Map join type → AQP skip label:
            {
                "Hash Join":   "no_hashjoin",
                "Merge Join":  "no_mergejoin",
                "Nested Loop": "no_nestloop",
            }
        - Call get_cost_comparison_reasons() with the correct skip_label
        - Build annotation:
            "This join is implemented using <join_type> (<join_kind> join).
             <condition if available>
             Alternatives were not chosen: <reasons>."
          OR if no reasons found (no cheaper AQP):
            "This join is implemented using <join_type>."
    """
    pass

# =============================================================================
# SECTION 5: OTHER OPERATIONS ANNOTATION
# =============================================================================

def annotate_others(qep_nodes: list) -> list:
    """
    Generates annotation strings for non-scan, non-join operations
    such as Sort, Aggregate, Limit, etc.

    Args:
        qep_nodes (list): Flat list of all QEP nodes (from parse_plan_nodes).

    Returns:
        list[str]: One annotation string per relevant node found.

    TODO:
        - Filter nodes where node["Node Type"] is in OTHER_NODES
        - Handle each type separately:
            * Sort:
                - Extract "Sort Key" list
                - "Results are sorted by: <keys>."
            * Aggregate / Hash Aggregate / Group Aggregate:
                - Extract "Strategy" if available
                - "Aggregation is performed using <strategy> strategy."
            * Limit:
                - "Result set is limited to a fixed number of rows (LIMIT clause)."
            * Unique:
                - "Duplicate rows are removed (DISTINCT or UNION clause)."
            * Materialize:
                - "Intermediate results are materialized (stored temporarily)
                   to avoid re-scanning."
            * Default fallback for anything else in OTHER_NODES:
                - "Operation: <node_type> (cost: <total_cost>)."
    """
    pass

# =============================================================================
# SECTION 6: MASTER ANNOTATION FUNCTION
# =============================================================================

def generate_annotations(qep: dict, aqps: dict) -> dict:
    """
    Master function that orchestrates all annotation steps.
    Called by interface.py after preprocessing fetches the QEP and AQPs.

    Args:
        qep (dict): The full QEP plan dict (output of get_qep).
        aqps (dict): Dict of AQP label → plan dict (output of get_all_aqps).

    Returns:
        dict: Structured annotation result with keys:
            {
                "scans":     list[str],   # scan annotations
                "joins":     list[str],   # join annotations
                "others":    list[str],   # other operation annotations
                "full_text": str          # all annotations joined as one string
            }

    TODO:
        - Call parse_plan_nodes(qep) to get a flat node list
        - Call get_root_cost(qep) to get the QEP's total cost
        - Call annotate_scans(nodes)
        - Call annotate_joins(nodes, aqps, qep_cost)
        - Call annotate_others(nodes)
        - Combine all lists into "full_text" using "\n".join()
        - Return the structured dict
    """
    pass

# =============================================================================
# SECTION 7: ENTRY POINT (for quick testing)
# =============================================================================

if __name__ == "__main__":
    # Quick test to verify annotation works end-to-end independently
    # TODO (for testing only):
    #   1. Import get_connection, get_qep, get_all_aqps from preprocessing
    #   2. Connect to DB
    #   3. Run a test query, e.g.:
    #      "SELECT * FROM customer C, orders O WHERE C.c_custkey = O.o_custkey"
    #   4. Fetch QEP and AQPs
    #   5. Call generate_annotations(qep, aqps)
    #   6. Print result["full_text"] — verify it produces readable annotations
    #   7. Close connection
    qep  = get_dummy_qep()   # ← swap to get_qep(conn, sql) when ready
    aqps = get_dummy_aqps()  # ← swap to get_all_aqps(conn, sql) when ready
    result = generate_annotations(qep, aqps)
    print(result["full_text"])
    pass