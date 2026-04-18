# annotation.py
# Responsibilities:
#   - Receive parsed QEP and AQPs from preprocessing.py
#   - Identify operators used in the QEP (scans, joins, aggregations, sorts, etc.)
#   - Compare QEP costs against AQP costs to explain WHY operators were chosen
#   - Generate human-readable annotation strings for each SQL clause/component
#   - Return a structured annotation result to interface.py

import re
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
    if qep_cost <= 0 or qep_cost == float("inf"):
        return 0.0
    if aqp_cost == float("inf"):
        return float("inf")
    return round(aqp_cost / qep_cost, 1)


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
    """
    reasons = []
    for label, plan in aqps.items():
        if label == skip_label or plan is None:
            continue
        aqp_cost = get_root_cost(plan)
        ratio = compare_costs(qep_cost, aqp_cost)
        if ratio > 1.0:
            alt_name = AQP_LABEL_MAP.get(label, label)
            reasons.append(f"{alt_name} costs ~{ratio}x more")
    return reasons

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
    """
    annotations = []
    for node in qep_nodes:
        node_type = node.get("Node Type", "")
        if node_type not in SCAN_NODES:
            continue

        table = node.get("Relation Name", "unknown")
        index = node.get("Index Name", "")
        filter_cond = node.get("Filter", "")

        if node_type == "Seq Scan":
            text = (f"Table '{table}' is read using Sequential Scan. "
                    f"This is likely because no usable index exists on the filtered columns.")
        elif node_type in ("Index Scan", "Index Only Scan"):
            text = (f"Table '{table}' is accessed via {node_type} on '{index}'. "
                    f"An index was available and used to avoid a full table scan.")
        elif node_type == "Bitmap Heap Scan":
            text = (f"Table '{table}' is accessed via Bitmap Heap Scan. "
                    f"This handles multiple matching rows efficiently using a bitmap.")
        elif node_type == "Bitmap Index Scan":
            idx = f" on '{index}'" if index else ""
            text = f"A Bitmap Index Scan{idx} is used to build a bitmap of matching rows."
        else:
            text = f"Table '{table}' is accessed using {node_type}."

        if filter_cond:
            text += f" Filter applied: {filter_cond}"

        annotations.append(text)
    return annotations

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
    """
    annotations = []
    skip_map = {
        "Hash Join":   "no_hashjoin",
        "Merge Join":  "no_mergejoin",
        "Nested Loop": "no_nestloop",
    }

    for node in qep_nodes:
        node_type = node.get("Node Type", "")
        if node_type not in JOIN_NODES:
            continue

        join_kind = node.get("Join Type", "")

        condition = ""
        if node_type == "Hash Join":
            condition = node.get("Hash Cond", "")
        elif node_type == "Merge Join":
            condition = node.get("Merge Cond", "")
        elif node_type == "Nested Loop":
            condition = node.get("Join Filter", "")

        skip_label = skip_map.get(node_type)
        reasons = get_cost_comparison_reasons(qep_cost, aqps, skip_label)

        kind_str = f" ({join_kind} join)" if join_kind else ""
        text = f"This join is implemented using {node_type}{kind_str}."

        if condition:
            text += f" Join condition: {condition}."

        if reasons:
            text += f" Alternatives not chosen: {'; '.join(reasons)}."

        annotations.append(text)
    return annotations

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
    """
    annotations = []
    for node in qep_nodes:
        node_type = node.get("Node Type", "")
        if node_type not in OTHER_NODES:
            continue

        if node_type == "Sort":
            keys = node.get("Sort Key", [])
            text = f"Results are sorted by: {', '.join(keys)}."
        elif node_type in ("Aggregate", "Hash Aggregate", "Group Aggregate"):
            strategy = node.get("Strategy", node_type)
            text = f"Aggregation is performed using {strategy} strategy."
        elif node_type == "Limit":
            text = "Result set is limited to a fixed number of rows (LIMIT clause)."
        elif node_type == "Unique":
            text = "Duplicate rows are removed (DISTINCT or UNION clause)."
        elif node_type == "Materialize":
            text = ("Intermediate results are materialized (stored temporarily) "
                    "to avoid re-scanning.")
        else:
            cost = node.get("Total Cost", "N/A")
            text = f"Operation: {node_type} (cost: {cost})."

        annotations.append(text)
    return annotations

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

    """
    nodes = parse_plan_nodes(qep)
    qep_cost = get_root_cost(qep)

    scans = annotate_scans(nodes)
    joins = annotate_joins(nodes, aqps, qep_cost)
    others = annotate_others(nodes)

    full_text = "\n".join(scans + joins + others)
    return {
        "scans": scans,
        "joins": joins,
        "others": others,
        "clause_map": [],
        "full_text": full_text,
    }

def generate_annotations_with_sql(qep: dict, aqps: dict, sql: str) -> dict:
    """Extended version that also populates clause_map for inline SQL annotation."""
    result = generate_annotations(qep, aqps)
    nodes  = parse_plan_nodes(qep)
    result["clause_map"] = map_sql_clauses(sql, nodes)
    return result
# =============================================================================
# SECTION 7: SQL CLAUSE-LEVEL ANNOTATION
# =============================================================================

def map_sql_clauses(sql: str, qep_nodes: list) -> list:
    """
    Maps each line of the SQL query to a relevant QEP annotation.
    Returns list of (original_sql_line, annotation_str_or_None).
    """
    _SQL_KEYWORDS = {
        "select","from","where","join","inner","outer","left","right","cross",
        "on","and","or","not","as","in","is","null","between","like","exists",
        "all","any","distinct","having","union","intersect","except","with",
        "by","asc","desc","case","when","then","else","end","true","false",
        "limit","offset","group","order","into","count","sum","avg","min","max",
    }

    lines = sql.splitlines()
    scan_notes, join_notes, other_map = {}, [], {}

    for node in qep_nodes:
        ntype = node.get("Node Type", "")
        table = node.get("Relation Name", "")
        alias = node.get("Alias", table)
        index = node.get("Index Name", "")

        if ntype == "Seq Scan":
            note = f"[{table}] Sequential Scan (no usable index)"
        elif ntype in ("Index Scan", "Index Only Scan"):
            note = f"[{table}] {ntype} on '{index}'"
        elif ntype == "Bitmap Heap Scan":
            note = f"[{table}] Bitmap Heap Scan"
        elif ntype == "Bitmap Index Scan":
            note = f"[{table}] Bitmap Index Scan on '{index}'"
        elif ntype == "Tid Scan":
            note = f"[{table}] TID Scan"
        else:
            note = None

        if note and table:
            tl, al = table.lower(), (alias.lower() if alias else table.lower())
            scan_notes[tl] = note
            if al != tl:
                scan_notes[al] = note

        if ntype in ("Hash Join", "Merge Join", "Nested Loop"):
            cond = (node.get("Hash Cond") or node.get("Merge Cond")
                    or node.get("Join Filter") or "")
            join_notes.append((ntype, cond))
        elif ntype == "Sort":
            other_map["order"] = f"Sort by: {', '.join(node.get('Sort Key', []))}"
        elif ntype in ("Aggregate", "Hash Aggregate", "Group Aggregate"):
            other_map["group"] = f"Aggregation ({node.get('Strategy', ntype)} strategy)"
        elif ntype == "Limit":
            other_map["limit"] = "Result limited (LIMIT clause)"

    def _collect(text):
        found, seen = [], set()
        for tok in re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', text):
            tl = tok.lower()
            if tl in scan_notes and tl not in _SQL_KEYWORDS:
                n = scan_notes[tl]
                if n not in seen:
                    found.append(n); seen.add(n)
        return " | ".join(found)

    result, join_idx, in_from = [], 0, False

    for raw_line in lines:
        sl, annotation = raw_line.strip().lower(), None
        if not sl:
            result.append((raw_line, None)); continue
        fw = sl.split()[0]

        if fw == "select":
            in_from = False
        elif fw == "from":
            in_from = True
            annotation = _collect(sl) or None
        elif in_from and fw not in ("where","group","order","having","limit",
                "join","inner","left","right","cross","union","select","with","on","and","or"):
            annotation = _collect(sl.lstrip(",")) or None
        elif "join" in sl and fw not in ("where","on","and","or"):
            in_from = False
            parts = []
            ann = _collect(sl)
            if ann: parts.append(ann)
            if join_idx < len(join_notes):
                jtype, jcond = join_notes[join_idx]; join_idx += 1
                parts.append(f"→ {jtype}" + (f" on {jcond}" if jcond else ""))
            annotation = " | ".join(parts) or None
        elif fw in ("where", "on"):
            in_from = False
            if join_idx < len(join_notes):
                jtype, jcond = join_notes[join_idx]; join_idx += 1
                annotation = f"→ {jtype}" + (f" on {jcond}" if jcond else "")
        elif fw in ("and", "or") and join_idx < len(join_notes):
            jtype, jcond = join_notes[join_idx]; join_idx += 1
            annotation = f"→ {jtype}" + (f" on {jcond}" if jcond else "")
        elif fw == "order":
            in_from = False; annotation = other_map.get("order")
        elif fw == "group":
            in_from = False; annotation = other_map.get("group")
        elif fw == "limit":
            in_from = False; annotation = other_map.get("limit")
        else:
            if fw not in ("having","case","when","then","else","end"):
                in_from = False

        result.append((raw_line, annotation))
    return result
# =============================================================================
# SECTION 8: ENTRY POINT (for quick testing)
# =============================================================================

if __name__ == "__main__":
    # --- Dummy data test ---
    print("=== Dummy Data Test ===")
    qep  = get_dummy_qep()
    aqps = get_dummy_aqps()
    result = generate_annotations(qep, aqps)
    print(result["full_text"])
    print(f"\nScans: {len(result['scans'])}, Joins: {len(result['joins'])}, Others: {len(result['others'])}")

    # --- Real data test ---
    print("\n=== Real Data Test ===")
    from preprocessing import get_connection, close_connection, get_qep, get_all_aqps
    conn = get_connection()
    try:
        sql = "SELECT * FROM customer C, orders O WHERE C.c_custkey = O.o_custkey"
        qep = get_qep(conn, sql)
        aqps = get_all_aqps(conn, sql)
        result = generate_annotations(qep, aqps)
        print(result["full_text"])
        print(f"\nScans: {len(result['scans'])}, Joins: {len(result['joins'])}, Others: {len(result['others'])}")
    finally:
        close_connection(conn)