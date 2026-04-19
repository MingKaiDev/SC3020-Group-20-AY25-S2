import re
from preprocessing import parse_plan_nodes, get_root_cost

# =============================================================================
# SECTION 1: CONSTANTS
# =============================================================================

# Node type categories
SCAN_NODES = {
    "Seq Scan", "Index Scan", "Index Only Scan",
    "Bitmap Heap Scan", "Bitmap Index Scan", "Tid Scan",
}

JOIN_NODES = {"Hash Join", "Merge Join", "Nested Loop"}

OTHER_NODES = {
    "Aggregate", "Hash Aggregate", "Group Aggregate",
    "Sort", "Limit", "Unique", "Hash", "Materialize",
    "Gather", "Gather Merge", "Subquery Scan",
    "BitmapAnd", "BitmapOr",
}

# AQP label -> human-readable description of what was disabled.
# "no_hashjoin" means PostgreSQL produced a plan WITHOUT Hash Join.
AQP_LABEL_MAP = {
    "no_hashjoin": "without Hash Join",
    "no_mergejoin": "without Merge Join",
    "no_nestloop": "without Nested Loop",
    "no_seqscan": "without Sequential Scan",
    "no_indexscan": "without Index Scan",
}

# =============================================================================
# SECTION 2: COST COMPARISON HELPERS
# =============================================================================

def compare_costs(qep_cost: float, aqp_cost: float) -> float:
    """Computes how many times more expensive an AQP is compared to the QEP."""
    if qep_cost is None or aqp_cost is None:
        return 0.0
    if qep_cost <= 0 or qep_cost == float("inf"):
        return 0.0
    # Guard against NaN
    if aqp_cost != aqp_cost or qep_cost != qep_cost:
        return 0.0
    if aqp_cost == float("inf"):
        return float("inf")
    return round(aqp_cost / qep_cost, 1)


def _format_cost(cost: float) -> str:
    """Format a cost value for human-readable display."""
    if cost is None:
        return "N/A"
    if cost == float("inf") or cost != cost:
        return "very high"
    return f"{cost:,.1f}"


def get_cost_comparison_reasons(qep_cost: float, aqps: dict, skip_label: str = None) -> list:
    """ Compares the QEP root cost against all available AQP root costs."""
    reasons = []
    for label, plan in (aqps or {}).items():
        if label == skip_label or plan is None:
            continue
        aqp_cost = get_root_cost(plan)
        ratio = compare_costs(qep_cost, aqp_cost)
        alt_desc = AQP_LABEL_MAP.get(label, label)
        if ratio == float("inf"):
            reasons.append(
                f"An alternative whole-query plan {alt_desc} has a very high "
                f"cost (QEP cost: {_format_cost(qep_cost)})."
            )
        elif ratio > 1.0:
            reasons.append(
                f"An alternative whole-query plan {alt_desc} costs about "
                f"{ratio}x the original plan "
                f"(QEP: {_format_cost(qep_cost)}, AQP: {_format_cost(aqp_cost)})."
            )
    return reasons

# =============================================================================
# SECTION 3: SCAN ANNOTATION
# =============================================================================

def annotate_scans(qep_nodes: list) -> list:
    """ Generates annotation strings for all scan operations found in the QEP."""
    annotations = []
    for node in qep_nodes:
        node_type = node.get("Node Type", "")
        if node_type not in SCAN_NODES:
            continue

        table = node.get("Relation Name", "unknown")
        alias = node.get("Alias", "")
        index = node.get("Index Name", "")
        filter_cond = node.get("Filter", "")
        index_cond = node.get("Index Cond", "")
        recheck_cond = node.get("Recheck Cond", "")
        rows_removed = node.get("Rows Removed by Filter", None)

        alias_str = f" (alias '{alias}')" if alias and alias != table else ""

        if node_type == "Seq Scan":
            text = (
                f"Table '{table}'{alias_str} is read using Sequential Scan. "
                f"PostgreSQL estimated that a sequential scan is the cheapest "
                f"strategy for this table. This may be because the table is small, "
                f"the filter is not very selective, or no useful index is available "
                f"for the filtered columns."
            )
        elif node_type == "Index Scan":
            text = (
                f"Table '{table}'{alias_str} is accessed via Index Scan "
                f"using index '{index}'. PostgreSQL uses the index to locate "
                f"matching rows directly, avoiding a full table scan."
            )
        elif node_type == "Index Only Scan":
            text = (
                f"Table '{table}'{alias_str} is accessed via Index Only Scan "
                f"using index '{index}'. All required columns are available in "
                f"the index itself, so PostgreSQL does not need to read the "
                f"table heap pages."
            )
        elif node_type == "Bitmap Heap Scan":
            text = (
                f"Table '{table}'{alias_str} is accessed via Bitmap Heap Scan. "
                f"PostgreSQL first builds a bitmap of matching row locations "
                f"(using one or more Bitmap Index Scans), then reads the actual "
                f"rows from the heap in physical order for better I/O efficiency."
            )
        elif node_type == "Bitmap Index Scan":
            idx_str = f" on index '{index}'" if index else ""
            text = (
                f"A Bitmap Index Scan{idx_str} is used to build a bitmap of "
                f"matching row locations. This bitmap is passed to a Bitmap "
                f"Heap Scan for the actual row retrieval."
            )
        elif node_type == "Tid Scan":
            text = (
                f"Table '{table}'{alias_str} is accessed via TID Scan, which "
                f"directly fetches rows by their physical tuple identifier. "
                f"This is very fast but only applicable when the query "
                f"references ctid directly."
            )
        else:
            text = f"Table '{table}'{alias_str} is accessed using {node_type}."

        # Append condition details
        if index_cond:
            text += f" Index condition: {index_cond}."
        if recheck_cond:
            text += f" Recheck condition: {recheck_cond}."
        if filter_cond:
            text += f" Filter applied: {filter_cond}."
        if rows_removed is not None:
            text += f" Rows removed by filter: {rows_removed}."

        annotations.append(text)
    return annotations

# =============================================================================
# SECTION 4: JOIN ANNOTATION
# =============================================================================

def annotate_joins(qep_nodes: list, aqps: dict, qep_cost: float) -> list:
    """ Generates annotation strings for all join operations found in the QEP. """
    annotations = []
    join_types_seen = set()

    _join_aqp_map = {
        "Hash Join":    "no_hashjoin",
        "Merge Join":   "no_mergejoin",
        "Nested Loop":  "no_nestloop",
    }

    for node in qep_nodes:
        node_type = node.get("Node Type", "")
        if node_type not in JOIN_NODES:
            continue

        join_types_seen.add(node_type)
        join_kind = node.get("Join Type", "")

        # Extract the relevant join condition
        condition = ""
        join_filter = node.get("Join Filter", "")
        if node_type == "Hash Join":
            condition = node.get("Hash Cond", "")
        elif node_type == "Merge Join":
            condition = node.get("Merge Cond", "")
        elif node_type == "Nested Loop":
            condition = node.get("Join Filter", "") or node.get("Filter", "")

        # Build the main description
        kind_str = f" ({join_kind})" if join_kind else ""

        if node_type == "Hash Join":
            text = (
                f"A Hash Join{kind_str} is used. PostgreSQL builds a hash "
                f"table on one input and probes it with rows from the other."
            )
        elif node_type == "Merge Join":
            text = (
                f"A Merge Join{kind_str} is used. Both inputs are sorted on "
                f"the join key and merged together in a single pass."
            )
        elif node_type == "Nested Loop":
            text = (
                f"A Nested Loop{kind_str} join is used. For each row from "
                f"the outer input, PostgreSQL scans the inner input for "
                f"matching rows."
            )
        else:
            text = f"Join is implemented using {node_type}{kind_str}."

        if condition:
            text += f" Join condition: {condition}."
        if join_filter and join_filter != condition:
            text += f" Join filter: {join_filter}."

        # Append the intermediate node cost for this specific join node.
        node_cost = node.get("Total Cost")
        if node_cost is not None:
            text += f" Node cost: {_format_cost(node_cost)}."

        annotations.append(text)

    # AQP comparison summary (one entry per join operator type) 
    if join_types_seen and aqps:
        summary_lines = []
        for jtype in ("Hash Join", "Merge Join", "Nested Loop"):
            if jtype not in join_types_seen:
                continue
            label = _join_aqp_map.get(jtype)
            if not label or label not in aqps or aqps[label] is None:
                continue
            aqp_cost = get_root_cost(aqps[label])
            ratio = compare_costs(qep_cost, aqp_cost)
            alt_desc = AQP_LABEL_MAP.get(label, label)
            if ratio == float("inf"):
                summary_lines.append(
                    f"A plan {alt_desc} has a very high cost "
                    f"(QEP root cost: {_format_cost(qep_cost)})."
                )
            elif ratio > 1.0:
                summary_lines.append(
                    f"A plan {alt_desc} costs about {ratio}x the original "
                    f"whole-query plan (QEP root cost: {_format_cost(qep_cost)}, "
                    f"AQP root cost: {_format_cost(aqp_cost)})."
                )
        if summary_lines:
            annotations.append(
                "AQP comparison summary: " + " ".join(summary_lines)
            )

    return annotations

# =============================================================================
# SECTION 5: OTHER OPERATIONS ANNOTATION
# =============================================================================

def annotate_others(qep_nodes: list) -> list:
    """ Generates annotation strings for non-scan, non-join operations such as Sort, Aggregate, Limit, Hash, Materialize, etc."""
    annotations = []
    seen_aggregate_keys = set()

    for node in qep_nodes:
        node_type = node.get("Node Type", "")
        if node_type not in OTHER_NODES:
            continue

        # Skip standalone Hash nodes as they are internal to Hash Join.
        if node_type == "Hash":
            continue

        if node_type == "Sort":
            keys = node.get("Sort Key", [])
            if keys:
                text = (
                    f"Results are sorted by: {', '.join(keys)}. "
                    f"PostgreSQL performs a sort operation to satisfy "
                    f"ORDER BY or as preparation for a merge-based operation."
                )
            else:
                text = (
                    "A Sort operation is performed. "
                    "PostgreSQL sorts the rows, possibly for ORDER BY "
                    "or as preparation for a merge-based operation."
                )

        elif node_type in ("Aggregate", "Hash Aggregate", "Group Aggregate"):
            strategy = node.get("Strategy", "")
            group_keys = node.get("Group Key", [])
            agg_key = (node_type, strategy, tuple(group_keys))
            if agg_key in seen_aggregate_keys:
                continue
            seen_aggregate_keys.add(agg_key)
            if group_keys:
                text = (
                    f"The query performs aggregation grouped by: "
                    f"{', '.join(group_keys)}."
                )
            else:
                text = "The query performs aggregation."
            if strategy:
                text += (
                    f" PostgreSQL uses the '{strategy}' aggregation strategy "
                    f"in the selected plan."
                )

        elif node_type == "Limit":
            rows = node.get("Plan Rows", "")
            if rows:
                text = (
                    f"A Limit operation returns only a subset of rows "
                    f"(up to {rows} rows). This corresponds to the LIMIT "
                    f"clause in the SQL query."
                )
            else:
                text = (
                    "A Limit operation restricts the number of rows returned. "
                    "This corresponds to the LIMIT clause in the SQL query."
                )

        elif node_type == "Unique":
            text = (
                "A Unique operation removes consecutive duplicate rows from "
                "sorted input. This typically corresponds to a DISTINCT clause "
                "or is used after a UNION to eliminate duplicates."
            )

        elif node_type == "Materialize":
            text = (
                "Intermediate results are materialized (stored temporarily in "
                "memory or on disk) so they can be re-scanned without "
                "recomputing."
            )

        elif node_type == "Gather":
            workers = node.get("Workers Planned", "")
            w_str = f" with {workers} worker(s)" if workers else ""
            text = (
                f"A Gather operation{w_str} collects results from parallel "
                f"worker processes into a single stream."
            )

        elif node_type == "Gather Merge":
            workers = node.get("Workers Planned", "")
            w_str = f" with {workers} worker(s)" if workers else ""
            text = (
                f"A Gather Merge operation{w_str} collects pre-sorted results "
                f"from parallel workers and merges them into a single sorted "
                f"stream."
            )

        elif node_type == "Subquery Scan":
            alias = node.get("Alias", "")
            a_str = f" on '{alias}'" if alias else ""
            text = (
                f"A Subquery Scan{a_str} reads the output of a subquery or "
                f"CTE (Common Table Expression) as if it were a table."
            )

        elif node_type == "BitmapAnd":
            text = (
                "A BitmapAnd operation combines multiple bitmap index results "
                "using a logical AND, only rows matching all conditions are kept."
            )

        elif node_type == "BitmapOr":
            text = (
                "A BitmapOr operation combines multiple bitmap index results "
                "using a logical OR, rows matching any condition are kept."
            )

        else:
            cost = node.get("Total Cost", "N/A")
            text = f"Operation: {node_type} (cost: {cost})."

        annotations.append(text)
    return annotations

# =============================================================================
# SECTION 6: MASTER ANNOTATION FUNCTION
# =============================================================================

def generate_annotations(qep: dict, aqps: dict, sql: str) -> dict:
    """
    Master function that orchestrates all annotation steps.
    Called by interface.py after preprocessing fetches the QEP and AQPs.

    """
    nodes = parse_plan_nodes(qep)
    qep_cost = get_root_cost(qep)

    scans = annotate_scans(nodes)
    joins = annotate_joins(nodes, aqps or {}, qep_cost)
    others = annotate_others(nodes)
    clause_map = map_sql_clauses(sql or "", nodes)
    full_text = "\n".join(scans + joins + others)

    return {
        "scans": scans,
        "joins": joins,
        "others": others,
        "clause_map": clause_map,
        "full_text": full_text,
    }

# =============================================================================
# SECTION 7: SQL CLAUSE-LEVEL ANNOTATION
# =============================================================================

def _extract_join_tokens(condition: str) -> set:
    """Extract normalised column-name tokens from a join condition string."""
    s = condition.lower()
    # Remove parentheses and casts like ::bigint
    s = re.sub(r'::\w+', '', s)
    s = s.replace("(", " ").replace(")", " ")
    # Extract dotted column refs (alias.column) -> keep only column part
    tokens = set()
    for m in re.finditer(r'([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)', s):
        tokens.add(m.group(2))
    # Also grab bare identifiers that look like column names (contain _)
    if not tokens:
        for m in re.finditer(r'\b([a-z_][a-z0-9_]*)\b', s):
            tok = m.group(1)
            if '_' in tok:
                tokens.add(tok)
    return tokens


def _match_join_condition(sql_on_cond: str, qep_cond: str) -> bool:
    """ Returns True if the SQL ON condition and QEP join condition refer to the
    same column pair. Robust to case, parens, whitespace, alias differences,
    and operand order reversal (a = b vs b = a)."""
    sql_tokens = _extract_join_tokens(sql_on_cond)
    qep_tokens = _extract_join_tokens(qep_cond)
    if not sql_tokens or not qep_tokens:
        return False
    # High-confidence match: all SQL ON tokens appear in QEP condition
    return sql_tokens <= qep_tokens or qep_tokens <= sql_tokens


def map_sql_clauses(sql: str, qep_nodes: list) -> list:
    """Maps each line of the SQL query to a relevant QEP annotation."""
    _SQL_KEYWORDS = {
        "select", "from", "where", "join", "inner", "outer", "left", "right",
        "cross", "on", "and", "or", "not", "as", "in", "is", "null",
        "between", "like", "exists", "all", "any", "distinct", "having",
        "union", "intersect", "except", "with", "by", "asc", "desc", "case",
        "when", "then", "else", "end", "true", "false", "limit", "offset",
        "group", "order", "into", "count", "sum", "avg", "min", "max",
    }

    lines = sql.splitlines()
    scan_notes, join_notes, other_map = {}, [], {}
    has_unique = False

    for node in qep_nodes:
        ntype = node.get("Node Type", "")
        table = node.get("Relation Name", "")
        alias = node.get("Alias", table)
        index = node.get("Index Name", "")

        if ntype == "Seq Scan":
            note = f"[{table}] Sequential Scan (estimated cheapest strategy)"
        elif ntype in ("Index Scan", "Index Only Scan"):
            note = f"[{table}] {ntype} on '{index}'"
        elif ntype == "Bitmap Heap Scan":
            note = f"[{table}] Bitmap Heap Scan"
        elif ntype == "Bitmap Index Scan":
            note = f"Bitmap Index Scan on '{index}'"
        elif ntype == "Tid Scan":
            note = f"[{table}] TID Scan"
        else:
            note = None

        if note and table:
            tl = table.lower()
            al = alias.lower() if alias else tl
            scan_notes[tl] = note
            if al != tl:
                scan_notes[al] = note

        # Collect join nodes with ALL available conditions for matching.
        if ntype in JOIN_NODES:
            cond = (node.get("Hash Cond") or node.get("Merge Cond")
                    or node.get("Join Filter") or node.get("Filter") or "")
            join_notes.append((ntype, cond))
        elif ntype == "Sort":
            keys = node.get("Sort Key", [])
            other_map.setdefault("order", f"Sort by: {', '.join(keys)}" if keys else "Sort")
        elif ntype in ("Aggregate", "Hash Aggregate", "Group Aggregate"):
            gk = node.get("Group Key", [])
            strat = node.get("Strategy", ntype)
            ann = f"Aggregation ({strat})"
            if gk:
                ann += f" on {', '.join(gk)}"
            other_map.setdefault("group", ann)
        elif ntype == "Limit":
            other_map.setdefault("limit", "Result limited (LIMIT clause)")
        elif ntype == "Unique":
            has_unique = True
            other_map.setdefault("distinct", "Duplicate removal (DISTINCT)")

    # Track which join_notes have been matched by condition
    used_join = [False] * len(join_notes)

    def _collect(text):
        found, seen = [], set()
        for tok in re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', text):
            tl = tok.lower()
            if tl in scan_notes and tl not in _SQL_KEYWORDS:
                n = scan_notes[tl]
                if n not in seen:
                    found.append(n)
                    seen.add(n)
        return " | ".join(found)

    def _extract_sql_on_condition(line: str) -> str:
        """Extract the ON condition from a SQL JOIN line"""
        m = re.search(r'\bON\b\s+(.+)', line, re.IGNORECASE)
        return m.group(1).strip().rstrip(";") if m else ""

    def _find_best_join(sql_on_cond: str):
        """Find the QEP join note whose condition best matches the SQL ON condition. Returns (index, jtype, jcond) or None."""
        if not sql_on_cond:
            return None
        for i, (jtype, jcond) in enumerate(join_notes):
            if used_join[i] or not jcond:
                continue
            if _match_join_condition(sql_on_cond, jcond):
                return (i, jtype, jcond)
        return None

    def _consume_next_unused_join():
        """Fallback: return the first unused join note sequentially."""
        for i, (jtype, jcond) in enumerate(join_notes):
            if not used_join[i]:
                return (i, jtype, jcond)
        return None

    result, in_from = [], False

    for raw_line in lines:
        sl = raw_line.strip().lower()
        annotation = None
        if not sl:
            result.append((raw_line, None))
            continue
        fw = sl.split()[0]

        if fw == "select":
            in_from = False
            # Check if SELECT DISTINCT
            if "distinct" in sl and has_unique:
                annotation = other_map.get("distinct")
        elif fw == "from":
            in_from = True
            annotation = _collect(sl) or None
        elif fw == "with":
            in_from = False
            # CTE no specific annotation
        elif in_from and fw not in (
            "where", "group", "order", "having", "limit",
            "join", "inner", "left", "right", "cross",
            "union", "select", "with", "on", "and", "or",
        ):
            annotation = _collect(sl.lstrip(",")) or None
        elif "join" in sl and fw not in ("where", "on", "and", "or"):
            in_from = False
            parts = []
            ann = _collect(sl)
            if ann:
                parts.append(ann)
            # Match by ON condition instead of consuming sequentially
            sql_on = _extract_sql_on_condition(raw_line)
            match = _find_best_join(sql_on)
            if match is None:
                # Fallback: sequential consumption
                match = _consume_next_unused_join()
            if match is not None:
                idx, jtype, jcond = match
                used_join[idx] = True
                parts.append(f"-> {jtype}" + (f" on {jcond}" if jcond else ""))
            annotation = " | ".join(parts) or None
        elif fw in ("where", "on"):
            in_from = False
            scan_ann = _collect(sl)
            if scan_ann:
                annotation = scan_ann
            else:
                # For standalone ON lines, try condition matching too
                sql_on = _extract_sql_on_condition(raw_line)
                match = _find_best_join(sql_on) if sql_on else None
                if match is None:
                    match = _consume_next_unused_join()
                if match is not None:
                    idx, jtype, jcond = match
                    used_join[idx] = True
                    annotation = f"-> {jtype}" + (f" on {jcond}" if jcond else "")
        elif fw == "order":
            in_from = False
            annotation = other_map.get("order")
        elif fw == "group":
            in_from = False
            annotation = other_map.get("group")
        elif fw == "having":
            in_from = False
            annotation = other_map.get("group")  # HAVING is tied to aggregation
        elif fw == "limit":
            in_from = False
            annotation = other_map.get("limit")
        elif fw == "distinct":
            annotation = other_map.get("distinct")
        else:
            if fw not in ("case", "when", "then", "else", "end"):
                in_from = False

        result.append((raw_line, annotation))
    return result
# =============================================================================
# SECTION 8: ENTRY POINT (for quick testing)
# =============================================================================

if __name__ == "__main__":
    from preprocessing import get_connection, close_connection, get_qep, get_all_aqps

    print("=== annotation.py smoke test (live DB) ===")
    conn = get_connection()
    try:
        sql = "SELECT * FROM customer C, orders O WHERE C.c_custkey = O.o_custkey"
        qep = get_qep(conn, sql)
        aqps = get_all_aqps(conn, sql)
        result = generate_annotations(qep, aqps, sql)
        print(result["full_text"])
        print(f"\nScans: {len(result['scans'])}, Joins: {len(result['joins'])}, "
              f"Others: {len(result['others'])}")
    finally:
        close_connection(conn)