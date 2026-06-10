"""
============================================================
Execution Plan Analyzer & Cost-Based Analysis
============================================================
Uses SQLite's EXPLAIN QUERY PLAN to generate execution plans,
extracts cost metrics, and compares query performance.
============================================================
"""

import time
import sqlite3


class ExecutionPlanAnalyzer:
    """
    Analyzes SQL query execution plans and measures performance.
    Uses EXPLAIN QUERY PLAN (SQLite) to inspect how the database
    engine processes each query.
    """

    def __init__(self, db_path):
        self.db_path = db_path

    def _get_connection(self):
        """Create a fresh connection for each analysis to avoid locking."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ── Execution Plan ────────────────────────────────────────

    def get_execution_plan(self, sql):
        """
        Run EXPLAIN QUERY PLAN and return a structured representation.
        Returns a list of plan nodes, each with id, parent, detail.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
            rows = cursor.fetchall()

            plan_nodes = []
            for row in rows:
                # SQLite EXPLAIN QUERY PLAN returns:
                #   (selectid, order, from, detail)
                node = {
                    "id": row[0],
                    "parent": row[1],
                    "subquery": row[2],
                    "detail": row[3] if len(row) > 3 else str(row),
                }
                plan_nodes.append(node)

            return {
                "nodes": plan_nodes,
                "readable": self._format_plan(plan_nodes),
                "raw": [list(r) for r in rows],
            }
        except Exception as e:
            return {"error": str(e), "nodes": [], "readable": f"Error: {e}", "raw": []}
        finally:
            conn.close()

    def _format_plan(self, nodes):
        """Format plan nodes into a human-readable tree string."""
        lines = []
        for i, node in enumerate(nodes):
            indent = "  " * node.get("subquery", 0)
            prefix = "├── " if i < len(nodes) - 1 else "└── "
            lines.append(f"{indent}{prefix}{node['detail']}")
        return "\n".join(lines) if lines else "Empty plan"

    # ── Detailed EXPLAIN (bytecode) ───────────────────────────

    def get_detailed_plan(self, sql):
        """
        Run EXPLAIN (full bytecode) to get low-level execution details.
        Returns the opcode listing that SQLite's VM will execute.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN {sql}")
            rows = cursor.fetchall()

            opcodes = []
            for row in rows:
                opcodes.append({
                    "addr": row[0],
                    "opcode": row[1],
                    "p1": row[2],
                    "p2": row[3],
                    "p3": row[4],
                    "p4": row[5] if len(row) > 5 else "",
                    "p5": row[6] if len(row) > 6 else "",
                    "comment": row[7] if len(row) > 7 else "",
                })
            return opcodes
        except Exception as e:
            return [{"error": str(e)}]
        finally:
            conn.close()

    # ── Cost Metrics ──────────────────────────────────────────

    def get_cost_metrics(self, sql):
        """
        Estimate cost metrics from the execution plan.
        SQLite doesn't expose cost numbers directly, so we derive
        proxies from plan details and table statistics.
        """
        conn = self._get_connection()
        try:
            plan = self.get_execution_plan(sql)
            metrics = {
                "scan_type": "unknown",
                "tables_accessed": [],
                "indexes_used": [],
                "estimated_rows": 0,
                "uses_index": False,
                "uses_covering_index": False,
                "uses_temp_btree": False,
                "subqueries": 0,
                "plan_steps": len(plan.get("nodes", [])),
            }

            cursor = conn.cursor()
            for node in plan.get("nodes", []):
                detail = node.get("detail", "").upper()

                # Detect scan types
                if "SCAN TABLE" in detail or "SCAN" in detail:
                    metrics["scan_type"] = "FULL TABLE SCAN"
                    # Extract table name
                    m = __import__("re").search(r"SCAN TABLE (\w+)", detail)
                    if m:
                        metrics["tables_accessed"].append(m.group(1))
                        # Get row count for cost estimation
                        try:
                            cursor.execute(
                                f"SELECT COUNT(*) FROM [{m.group(1)}]"
                            )
                            metrics["estimated_rows"] += cursor.fetchone()[0]
                        except Exception:
                            pass

                if "SEARCH TABLE" in detail or "SEARCH" in detail:
                    metrics["scan_type"] = "INDEX SEARCH"
                    metrics["uses_index"] = True
                    m = __import__("re").search(r"SEARCH TABLE (\w+)", detail)
                    if m:
                        metrics["tables_accessed"].append(m.group(1))

                if "USING INDEX" in detail or "USING COVERING INDEX" in detail:
                    metrics["uses_index"] = True
                    idx_m = __import__("re").search(
                        r"USING (?:COVERING )?INDEX (\w+)", detail
                    )
                    if idx_m:
                        metrics["indexes_used"].append(idx_m.group(1))

                if "COVERING INDEX" in detail:
                    metrics["uses_covering_index"] = True

                if "TEMP B-TREE" in detail:
                    metrics["uses_temp_btree"] = True

                if "SUBQUERY" in detail or "CORRELATED" in detail:
                    metrics["subqueries"] += 1

            # Compute a synthetic cost score (lower is better)
            cost = metrics["estimated_rows"]
            if metrics["scan_type"] == "FULL TABLE SCAN":
                cost *= 2  # Penalty for full scans
            if metrics["uses_temp_btree"]:
                cost *= 1.5  # Penalty for temp sorting
            if metrics["uses_index"]:
                cost *= 0.3  # Benefit from index usage
            if metrics["uses_covering_index"]:
                cost *= 0.1  # Covering index is very efficient
            metrics["estimated_cost"] = round(cost, 2)

            return metrics
        except Exception as e:
            return {"error": str(e), "estimated_cost": -1}
        finally:
            conn.close()

    # ── Performance Measurement ───────────────────────────────

    def measure_execution_time(self, sql, runs=5):
        """
        Execute the query multiple times and return timing statistics.
        Uses the median of *runs* executions for stability.
        """
        conn = self._get_connection()
        times = []
        row_count = 0

        try:
            for _ in range(runs):
                start = time.perf_counter()
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                end = time.perf_counter()
                times.append((end - start) * 1000)  # ms
                row_count = len(rows)

            times.sort()
            return {
                "min_ms": round(times[0], 4),
                "max_ms": round(times[-1], 4),
                "avg_ms": round(sum(times) / len(times), 4),
                "median_ms": round(times[len(times) // 2], 4),
                "runs": runs,
                "rows_returned": row_count,
            }
        except Exception as e:
            return {"error": str(e), "avg_ms": -1, "rows_returned": 0}
        finally:
            conn.close()

    # ── Full Comparison ───────────────────────────────────────

    def compare_queries(self, original_sql, optimized_sql):
        """
        Full side-by-side comparison of original vs optimized query.
        Returns plans, cost metrics, and timing for both.
        """
        result = {
            "original": {
                "sql": original_sql,
                "plan": self.get_execution_plan(original_sql),
                "cost": self.get_cost_metrics(original_sql),
                "timing": self.measure_execution_time(original_sql),
            },
            "optimized": {
                "sql": optimized_sql,
                "plan": self.get_execution_plan(optimized_sql),
                "cost": self.get_cost_metrics(optimized_sql),
                "timing": self.measure_execution_time(optimized_sql),
            },
        }

        # Compute improvement percentages
        orig_time = result["original"]["timing"].get("avg_ms", 0)
        opt_time = result["optimized"]["timing"].get("avg_ms", 0)

        if orig_time > 0:
            result["improvement"] = {
                "time_reduction_pct": round(
                    ((orig_time - opt_time) / orig_time) * 100, 2
                ),
                "original_avg_ms": orig_time,
                "optimized_avg_ms": opt_time,
            }
        else:
            result["improvement"] = {
                "time_reduction_pct": 0,
                "original_avg_ms": orig_time,
                "optimized_avg_ms": opt_time,
            }

        return result
