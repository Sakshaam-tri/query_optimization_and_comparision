"""
============================================================
Heuristic Query Optimization Engine
============================================================
Implements rule-based SQL query transformations:
  1. Remove Redundant Conditions  - eliminates tautologies (1=1, TRUE)
  2. Projection Pushdown          - replaces SELECT * with specific columns
  3. Selection Pushdown            - moves WHERE predicates closer to base tables
  4. Join Reordering               - processes smaller tables first
============================================================
"""

import re
import sqlparse


# ── Helper Data Class ─────────────────────────────────────────

class OptimizationStep:
    """Represents a single optimization transformation step."""

    def __init__(self, rule_name, description, before_query, after_query):
        self.rule_name = rule_name
        self.description = description
        self.before_query = before_query
        self.after_query = after_query

    def to_dict(self):
        return {
            "rule": self.rule_name,
            "description": self.description,
            "before": self.before_query,
            "after": self.after_query,
        }


# ── Main Optimizer Class ──────────────────────────────────────

class HeuristicOptimizer:
    """
    Applies heuristic-based transformations to SQL SELECT queries.
    Each rule is applied sequentially; every transformation is logged
    as an OptimizationStep for the UI to display.
    """

    def __init__(self, db_connection=None):
        self.steps = []
        self.db = db_connection
        self.table_sizes = {}
        self.table_columns = {}
        if db_connection:
            self._load_table_statistics()

    # ── Table Statistics ──────────────────────────────────────

    def _load_table_statistics(self):
        """Load table row counts and column names for optimization decisions."""
        try:
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = cursor.fetchall()
            for (table_name,) in tables:
                # Row count
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                self.table_sizes[table_name.lower()] = cursor.fetchone()[0]
                # Column info
                cursor.execute(f"PRAGMA table_info([{table_name}])")
                cols = cursor.fetchall()
                self.table_columns[table_name.lower()] = [c[1] for c in cols]
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────

    def optimize(self, sql):
        """
        Run all heuristic rules on *sql* and return
        (optimized_sql, list[dict])  where each dict is a step.
        """
        self.steps = []
        current = self._normalize(sql)

        current = self._rule_remove_redundant(current)
        current = self._rule_projection_pushdown(current)
        current = self._rule_selection_pushdown(current)
        current = self._rule_join_reordering(current)

        # If nothing changed, add a note
        if not self.steps:
            self.steps.append(OptimizationStep(
                "No Optimization Needed",
                "The query is already in an optimal form. "
                "No heuristic transformations were applicable.",
                current, current,
            ))

        return current, [s.to_dict() for s in self.steps]

    # ── Utility helpers ───────────────────────────────────────

    @staticmethod
    def _normalize(sql):
        """Collapse whitespace and trim."""
        return re.sub(r"\s+", " ", sql).strip()

    @staticmethod
    def _tables_and_aliases(sql):
        """Return {alias_lower: table_name_lower} from FROM / JOIN clauses."""
        mapping = {}
        for m in re.finditer(
            r"(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?",
            sql, re.IGNORECASE,
        ):
            tbl = m.group(1).lower()
            alias = (m.group(2) or m.group(1)).lower()
            mapping[alias] = tbl
        return mapping

    @staticmethod
    def _split_conditions(where_text):
        """Split a WHERE body on top-level ANDs (ignoring nested parens)."""
        parts, depth, buf = [], 0, []
        for token in re.split(r"(\bAND\b)", where_text, flags=re.IGNORECASE):
            depth += token.count("(") - token.count(")")
            if token.strip().upper() == "AND" and depth == 0:
                parts.append(" ".join(buf).strip())
                buf = []
            else:
                buf.append(token)
        if buf:
            parts.append(" ".join(buf).strip())
        return [p for p in parts if p]

    # ── Rule 1: Remove Redundant Conditions ───────────────────

    def _rule_remove_redundant(self, sql):
        original = sql

        # Remove tautologies like 1=1, 1!=0, TRUE
        tautologies = [
            r"\bAND\s+1\s*=\s*1",
            r"1\s*=\s*1\s+AND\b",
            r"\bWHERE\s+1\s*=\s*1\s+AND\b",
            r"\bAND\s+TRUE\b",
            r"\bTRUE\s+AND\b",
        ]
        for pat in tautologies:
            replacement = "WHERE" if "WHERE" in pat and "AND" in pat.split("WHERE")[-1] else ""
            sql = re.sub(pat, replacement, sql, flags=re.IGNORECASE)

        # Standalone WHERE 1=1 with nothing after
        sql = re.sub(r"\bWHERE\s+1\s*=\s*1\s*$", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bWHERE\s+TRUE\s*$", "", sql, flags=re.IGNORECASE)

        # Remove duplicate AND conditions
        where_m = re.search(
            r"\bWHERE\s+(.+?)(?=\s+GROUP\b|\s+ORDER\b|\s+LIMIT\b|\s+HAVING\b|$)",
            sql, re.IGNORECASE | re.DOTALL,
        )
        if where_m:
            conds = self._split_conditions(where_m.group(1))
            seen, unique = set(), []
            for c in conds:
                key = c.strip().lower()
                if key not in seen:
                    seen.add(key)
                    unique.append(c.strip())
            if len(unique) < len(conds):
                new_where = " AND ".join(unique)
                sql = sql[: where_m.start(1)] + new_where + sql[where_m.end(1) :]

        sql = self._normalize(sql)
        if sql != original:
            self.steps.append(OptimizationStep(
                "Remove Redundant Conditions",
                "Removed tautological conditions (e.g., 1=1, TRUE) "
                "and eliminated duplicate predicates from the WHERE clause.",
                original, sql,
            ))
        return sql

    # ── Rule 2: Projection Pushdown ───────────────────────────

    def _rule_projection_pushdown(self, sql):
        original = sql

        if not re.search(r"\bSELECT\s+\*\s+FROM\b", sql, re.IGNORECASE):
            return sql

        aliases = self._tables_and_aliases(sql)
        if not aliases:
            return sql

        # Gather columns explicitly referenced outside SELECT
        referenced = set()
        # FROM ON conditions
        for m in re.finditer(r"\bON\s+(.+?)(?=\s+(?:LEFT|RIGHT|INNER|CROSS|JOIN|WHERE|GROUP|ORDER|LIMIT|HAVING)\b|$)", sql, re.IGNORECASE):
            referenced.update(re.findall(r"\w+\.\w+", m.group(1)))
        # WHERE
        wm = re.search(r"\bWHERE\s+(.+?)(?=\s+GROUP\b|\s+ORDER\b|\s+LIMIT\b|\s+HAVING\b|$)", sql, re.IGNORECASE)
        if wm:
            referenced.update(re.findall(r"\w+\.\w+", wm.group(1)))
        # GROUP BY / ORDER BY
        for kw in ("GROUP BY", "ORDER BY"):
            gm = re.search(rf"\b{kw}\s+(.+?)(?=\s+HAVING\b|\s+LIMIT\b|\s+ORDER\b|$)", sql, re.IGNORECASE)
            if gm:
                referenced.update(re.findall(r"\w+\.\w+", gm.group(1)))

        if not referenced:
            # Fallback: list all columns from all tables
            cols = []
            for alias, tbl in aliases.items():
                tbl_cols = self.table_columns.get(tbl, [])
                for c in tbl_cols:
                    cols.append(f"{alias}.{c}")
            if cols:
                col_str = ", ".join(cols)
                sql = re.sub(
                    r"\bSELECT\s+\*\s+FROM\b",
                    f"SELECT {col_str} FROM",
                    sql, count=1, flags=re.IGNORECASE,
                )
        else:
            col_str = ", ".join(sorted(referenced))
            sql = re.sub(
                r"\bSELECT\s+\*\s+FROM\b",
                f"SELECT {col_str} FROM",
                sql, count=1, flags=re.IGNORECASE,
            )

        sql = self._normalize(sql)
        if sql != original:
            self.steps.append(OptimizationStep(
                "Projection Pushdown",
                "Replaced SELECT * with only the columns referenced in "
                "WHERE, JOIN ON, GROUP BY, and ORDER BY clauses. "
                "This reduces disk I/O and memory usage by avoiding "
                "unnecessary column reads.",
                original, sql,
            ))
        return sql

    # ── Rule 3: Selection Pushdown ────────────────────────────

    def _rule_selection_pushdown(self, sql):
        original = sql

        if not re.search(r"\bJOIN\b", sql, re.IGNORECASE):
            return sql

        where_m = re.search(
            r"\bWHERE\s+(.+?)(?=\s+GROUP\b|\s+ORDER\b|\s+LIMIT\b|\s+HAVING\b|$)",
            sql, re.IGNORECASE | re.DOTALL,
        )
        if not where_m:
            return sql

        aliases = self._tables_and_aliases(sql)
        conditions = self._split_conditions(where_m.group(1))

        pushable = {}   # alias -> [cond, ...]
        remaining = []

        for cond in conditions:
            refs = set()
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\.", cond, re.IGNORECASE):
                    refs.add(alias)
            if len(refs) == 1:
                pushable.setdefault(list(refs)[0], []).append(cond)
            else:
                remaining.append(cond)

        if not pushable:
            return sql

        # Move single-table predicates into the JOIN … ON clause
        new_sql = sql
        for alias, conds in pushable.items():
            for cond in conds:
                # Remove from WHERE
                new_sql = re.sub(
                    rf"\s+AND\s+{re.escape(cond)}", "", new_sql, flags=re.IGNORECASE
                )
                new_sql = re.sub(
                    rf"{re.escape(cond)}\s+AND\s+", "", new_sql, flags=re.IGNORECASE
                )
                # Standalone condition in WHERE
                new_sql = re.sub(
                    rf"\bWHERE\s+{re.escape(cond)}\s*(?=\s+GROUP\b|\s+ORDER\b|\s+LIMIT\b|\s+HAVING\b|$)",
                    "", new_sql, flags=re.IGNORECASE,
                )

                # Append to the matching JOIN's ON clause
                join_pat = (
                    rf"(JOIN\s+\w+\s+(?:AS\s+)?{re.escape(alias)}\s+ON\s+"
                    rf"[^)]+?(?=\s+(?:LEFT|RIGHT|INNER|CROSS|JOIN|WHERE|GROUP|ORDER|LIMIT|HAVING)\b|$))"
                )
                jm = re.search(join_pat, new_sql, re.IGNORECASE)
                if jm:
                    new_sql = new_sql[: jm.end()] + f" AND {cond}" + new_sql[jm.end() :]

        # Clean up leftover empty WHERE
        new_sql = re.sub(
            r"\bWHERE\s+(?=GROUP\b|ORDER\b|LIMIT\b|HAVING\b|$)",
            "", new_sql, flags=re.IGNORECASE,
        )
        new_sql = self._normalize(new_sql)

        if new_sql != original:
            info_lines = []
            for alias, conds in pushable.items():
                tbl = aliases.get(alias, alias)
                info_lines.append(
                    f"  • Pushed to table '{tbl}' (alias '{alias}'): "
                    + ", ".join(conds)
                )
            self.steps.append(OptimizationStep(
                "Selection Pushdown",
                "Moved single-table WHERE predicates into the "
                "corresponding JOIN ON clause so they are evaluated "
                "earlier, reducing intermediate result sizes.\n"
                + "\n".join(info_lines),
                original, new_sql,
            ))
            return new_sql

        return sql

    # ── Rule 4: Join Reordering ───────────────────────────────

    def _rule_join_reordering(self, sql):
        if not self.table_sizes:
            return sql
        if not re.search(r"\bJOIN\b", sql, re.IGNORECASE):
            return sql

        original = sql
        aliases = self._tables_and_aliases(sql)

        # Extract individual JOIN clauses
        join_pat = (
            r"((?:INNER\s+|LEFT\s+|RIGHT\s+|CROSS\s+)?JOIN\s+(\w+)"
            r"\s+(?:AS\s+)?(\w+)\s+ON\s+.+?)"
            r"(?=\s+(?:INNER\s+|LEFT\s+|RIGHT\s+|CROSS\s+)?JOIN\b"
            r"|\s+WHERE\b|\s+GROUP\b|\s+ORDER\b|\s+LIMIT\b|\s+HAVING\b|$)"
        )
        joins = list(re.finditer(join_pat, sql, re.IGNORECASE))
        if len(joins) < 2:
            return sql

        join_info = []
        for m in joins:
            tbl = m.group(2).lower()
            size = self.table_sizes.get(tbl, float("inf"))
            join_info.append({
                "clause": m.group(1).strip(),
                "table": tbl,
                "alias": m.group(3),
                "size": size,
            })

        sorted_joins = sorted(join_info, key=lambda j: j["size"])
        original_order = [j["table"] for j in join_info]
        new_order = [j["table"] for j in sorted_joins]

        if original_order != new_order:
            # Build size report
            size_lines = [
                f"  • {j['table']}: {j['size']:,} rows" for j in sorted_joins
            ]

            self.steps.append(OptimizationStep(
                "Join Reordering",
                "Suggested reordering JOINs so smaller tables are "
                "joined first, reducing the size of intermediate results.\n"
                "Table sizes (ascending):\n" + "\n".join(size_lines),
                original, sql,
            ))

        return sql


# ── Cost-Based Optimizer Class ────────────────────────────────

class CostBasedOptimizer:
    """
    Applies cost-based evaluation to different query transformations.
    Generates multiple candidate plans and uses the ExecutionPlanAnalyzer
    to estimate their cost, selecting the lowest cost plan.
    """

    def __init__(self, db_connection=None, db_path=None):
        self.db = db_connection
        self.db_path = db_path
        self.steps = []
        if db_path:
            from analyzer import ExecutionPlanAnalyzer
            self.analyzer = ExecutionPlanAnalyzer(db_path)
        else:
            self.analyzer = None

    def optimize(self, sql):
        original = sql
        self.steps = []

        if not self.analyzer:
            return sql, []

        candidates = []
        candidates.append({"name": "Original Query", "sql": sql})

        # Generate candidates using different heuristic rule subsets
        h_opt = HeuristicOptimizer(db_connection=self.db)
        
        sql_proj = h_opt._rule_projection_pushdown(sql)
        if sql_proj != sql:
            candidates.append({"name": "Projection Pushdown Applied", "sql": sql_proj})

        sql_sel = h_opt._rule_selection_pushdown(sql)
        if sql_sel != sql:
            candidates.append({"name": "Selection Pushdown Applied", "sql": sql_sel})

        sql_join = h_opt._rule_join_reordering(sql)
        if sql_join != sql:
            candidates.append({"name": "Join Reordering Applied", "sql": sql_join})

        # Candidate: OR to UNION ALL rewrite (simple naive approach for demonstration)
        if re.search(r"\bOR\b", sql, re.IGNORECASE) and not re.search(r"\bUNION\b", sql, re.IGNORECASE):
            where_m = re.search(r"\bWHERE\s+(.+?)(?=\s+GROUP\b|\s+ORDER\b|\s+LIMIT\b|\s+HAVING\b|$)", sql, re.IGNORECASE | re.DOTALL)
            if where_m:
                cond = where_m.group(1)
                if " OR " in cond.upper():
                    parts = re.split(r"\bOR\b", cond, flags=re.IGNORECASE)
                    if len(parts) == 2:
                        base_query = sql[:where_m.start()]
                        tail = sql[where_m.end():]
                        union_sql = f"{base_query} WHERE {parts[0].strip()} {tail} \nUNION ALL \n{base_query} WHERE {parts[1].strip()} {tail}"
                        union_sql = re.sub(r"\s+", " ", union_sql).strip()
                        candidates.append({"name": "OR rewritten to UNION ALL", "sql": union_sql})

        # Apply all heuristics combined
        full_opt, _ = HeuristicOptimizer(db_connection=self.db).optimize(sql)
        if full_opt != sql:
            candidates.append({"name": "All Heuristics Combined", "sql": full_opt})

        # Ensure candidates are unique by sql
        unique_candidates = []
        seen_sql = set()
        for cand in candidates:
            c_sql = cand["sql"].strip()
            if c_sql not in seen_sql:
                seen_sql.add(c_sql)
                unique_candidates.append(cand)

        best_sql = sql
        best_cost = float("inf")
        best_name = "Original Query"
        evaluations = []

        # Evaluate each candidate's cost
        for cand in unique_candidates:
            metrics = self.analyzer.get_cost_metrics(cand["sql"])
            cost = metrics.get("estimated_cost", float("inf"))
            evaluations.append(f"• Candidate: {cand['name']} | Est. Cost: {cost}")
            
            if cost < best_cost:
                best_cost = cost
                best_sql = cand["sql"]
                best_name = cand["name"]

        conclusion = f"Conclusion: Selected '{best_name}' as the optimal execution plan."
        if best_sql == sql:
            conclusion = "Conclusion: The original query already has the optimal estimated cost."

        self.steps.append(OptimizationStep(
            "Cost-Based Evaluation",
            "Evaluated multiple execution strategies by computing synthetic cost metrics (derived from row estimations, scan types, and index usage).\n\n" +
            "\n".join(evaluations) + f"\n\n{conclusion}",
            original, best_sql,
        ))

        return best_sql, [s.to_dict() for s in self.steps]
