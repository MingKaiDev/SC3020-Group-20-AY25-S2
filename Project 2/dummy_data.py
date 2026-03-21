# dummy_data.py
# Provides hardcoded fake QEP and AQP data for parallel development.
# ALL members import from here during development.
# Once preprocessing.py is complete, swap these out for real function calls.
#
# USAGE:
#   from dummy_data import get_dummy_qep, get_dummy_aqps, DUMMY_SQL
#
# SWAP OUT WHEN READY:
#   Replace get_dummy_qep()  → get_qep(conn, sql)
#   Replace get_dummy_aqps() → get_all_aqps(conn, sql)

# =============================================================================
# SECTION 1: DUMMY SQL QUERY
# =============================================================================

DUMMY_SQL = """
SELECT *
FROM customer C, orders O
WHERE C.c_custkey = O.o_custkey
""".strip()


# =============================================================================
# SECTION 2: DUMMY QEP
# Simulates: EXPLAIN (ANALYZE, FORMAT JSON) <DUMMY_SQL>
# Represents: Hash Join → Seq Scan (customer) + Hash → Seq Scan (orders)
# =============================================================================

def get_dummy_qep() -> dict:
    """
    Returns a hardcoded fake QEP mimicking PostgreSQL's EXPLAIN JSON output.
    Simulates a Hash Join between customer and orders via sequential scans.

    Returns:
        dict: Fake QEP plan dict with same structure as real get_qep() output.
    """
    return {
        "Plan": {
            "Node Type": "Hash Join",
            "Join Type": "Inner",
            "Hash Cond": "(o.o_custkey = c.c_custkey)",
            "Startup Cost": 0.00,
            "Total Cost": 4523.18,
            "Plan Rows": 150000,
            "Plan Width": 220,
            "Actual Rows": 150000,
            "Actual Loops": 1,
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "orders",
                    "Alias": "o",
                    "Startup Cost": 0.00,
                    "Total Cost": 1000.00,
                    "Plan Rows": 150000,
                    "Plan Width": 100,
                    "Actual Rows": 150000,
                    "Actual Loops": 1
                },
                {
                    "Node Type": "Hash",
                    "Startup Cost": 0.00,
                    "Total Cost": 500.00,
                    "Plan Rows": 150000,
                    "Plan Width": 120,
                    "Plans": [
                        {
                            "Node Type": "Seq Scan",
                            "Relation Name": "customer",
                            "Alias": "c",
                            "Startup Cost": 0.00,
                            "Total Cost": 500.00,
                            "Plan Rows": 150000,
                            "Plan Width": 120,
                            "Actual Rows": 150000,
                            "Actual Loops": 1
                        }
                    ]
                }
            ]
        }
    }


# =============================================================================
# SECTION 3: DUMMY AQPs
# Simulates: get_all_aqps() with operators disabled one at a time
# Each AQP has a higher cost than the QEP to mimic real optimizer behavior
# =============================================================================

def get_dummy_aqps() -> dict:
    """
    Returns hardcoded fake AQPs mimicking get_all_aqps() output.
    Each entry simulates disabling one planner operator group.

    Returns:
        dict: Fake AQP dict with same structure as real get_all_aqps() output.
              Keys: "no_hashjoin", "no_mergejoin", "no_nestloop",
                    "no_seqscan", "no_indexscan"
    """
    return {
        # Disabling Hash Join → optimizer picks Merge Join (7x more expensive)
        "no_hashjoin": {
            "Plan": {
                "Node Type": "Merge Join",
                "Join Type": "Inner",
                "Merge Cond": "(c.c_custkey = o.o_custkey)",
                "Startup Cost": 0.00,
                "Total Cost": 31662.26,
                "Plan Rows": 150000,
                "Plan Width": 220,
                "Plans": [
                    {
                        "Node Type": "Sort",
                        "Sort Key": ["c.c_custkey"],
                        "Startup Cost": 0.00,
                        "Total Cost": 14000.00,
                        "Plan Rows": 150000,
                        "Plans": [
                            {
                                "Node Type": "Seq Scan",
                                "Relation Name": "customer",
                                "Total Cost": 500.00,
                                "Plan Rows": 150000
                            }
                        ]
                    },
                    {
                        "Node Type": "Sort",
                        "Sort Key": ["o.o_custkey"],
                        "Startup Cost": 0.00,
                        "Total Cost": 17662.26,
                        "Plan Rows": 150000,
                        "Plans": [
                            {
                                "Node Type": "Seq Scan",
                                "Relation Name": "orders",
                                "Total Cost": 1000.00,
                                "Plan Rows": 150000
                            }
                        ]
                    }
                ]
            }
        },

        # Disabling Merge Join → optimizer picks Hash Join (same as QEP, ~1x)
        "no_mergejoin": {
            "Plan": {
                "Node Type": "Hash Join",
                "Join Type": "Inner",
                "Hash Cond": "(o.o_custkey = c.c_custkey)",
                "Startup Cost": 0.00,
                "Total Cost": 4600.00,
                "Plan Rows": 150000,
                "Plan Width": 220,
                "Plans": []
            }
        },

        # Disabling Nested Loop → optimizer picks Hash Join (similar cost)
        "no_nestloop": {
            "Plan": {
                "Node Type": "Hash Join",
                "Join Type": "Inner",
                "Hash Cond": "(o.o_custkey = c.c_custkey)",
                "Startup Cost": 0.00,
                "Total Cost": 46230.00,
                "Plan Rows": 150000,
                "Plan Width": 220,
                "Plans": []
            }
        },

        # Disabling Seq Scan → returns None (no index exists on these tables)
        "no_seqscan": None,

        # Disabling Index Scan → same as QEP since no index exists anyway
        "no_indexscan": {
            "Plan": {
                "Node Type": "Hash Join",
                "Join Type": "Inner",
                "Total Cost": 4523.18,
                "Plan Rows": 150000,
                "Plans": []
            }
        }
    }


# =============================================================================
# SECTION 4: DUMMY CONNECTION STUB
# =============================================================================

class DummyConnection:
    """
    A fake connection object for members who don't have PostgreSQL set up yet.
    Prevents crashes when interface.py or project.py checks self.conn.

    USAGE:
        from dummy_data import DummyConnection
        self.conn = DummyConnection()   # in interface.py __init__
    """
    def close(self):
        print("[DummyConnection] close() called — no real DB connection.")

    def cursor(self):
        raise NotImplementedError("DummyConnection: use real get_connection() for DB calls.")


# =============================================================================
# SECTION 5: QUICK TEST
# =============================================================================

if __name__ == "__main__":
    # Verify dummy data has correct structure
    qep  = get_dummy_qep()
    aqps = get_dummy_aqps()

    print("=== QEP Root Node ===")
    print(f"  Node Type : {qep['Plan']['Node Type']}")
    print(f"  Total Cost: {qep['Plan']['Total Cost']}")
    print(f"  Children  : {len(qep['Plan']['Plans'])}")

    print("\n=== AQP Keys ===")
    for label, plan in aqps.items():
        cost = plan["Plan"]["Total Cost"] if plan else "N/A (None)"
        print(f"  {label:20s} → cost: {cost}")

    print("\nDummy data is good")
