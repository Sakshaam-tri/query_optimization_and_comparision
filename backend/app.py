"""
============================================================
SQL Query Optimization - Flask Backend Application
============================================================
Provides REST API endpoints for:
  - Query optimization (heuristic rules)
  - Execution plan analysis (EXPLAIN)
  - Cost-based comparison
  - Performance measurement
  - Database initialization with sample data
============================================================
"""

import os
import sqlite3
import random
import string
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from optimizer import HeuristicOptimizer, CostBasedOptimizer
from analyzer import ExecutionPlanAnalyzer

# ── App Configuration ─────────────────────────────────────────

app = Flask(__name__, static_folder=None)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "..", "database")
DB_PATH = os.path.join(DB_DIR, "query_optimizer.db")
SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")
SAMPLE_DATA_PATH = os.path.join(DB_DIR, "sample_data.sql")
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")


# ── Database Helpers ──────────────────────────────────────────

def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    """Initialize database with schema and sample data."""
    conn = get_db()
    cursor = conn.cursor()

    # Run schema
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r") as f:
            cursor.executescript(f.read())

    # Run static sample data (Departments, Professors, Courses)
    if os.path.exists(SAMPLE_DATA_PATH):
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM Departments")
        if cursor.fetchone()[0] == 0:
            with open(SAMPLE_DATA_PATH, "r") as f:
                cursor.executescript(f.read())

    # Generate large dynamic datasets
    cursor.execute("SELECT COUNT(*) FROM Students")
    if cursor.fetchone()[0] == 0:
        _generate_students(cursor, count=2000)
        _generate_enrollments(cursor, count=8000)
        _generate_marks(cursor, count=8000)
        _generate_orders(cursor, count=10000)

    conn.commit()
    conn.close()
    print(f"[OK] Database initialized at {DB_PATH}")


def _random_name():
    """Generate a random student name."""
    first_names = [
        "Aarav", "Aditi", "Amit", "Ananya", "Arjun", "Deepa", "Gaurav",
        "Ishaan", "Kavya", "Lakshmi", "Meera", "Nikhil", "Priya", "Rahul",
        "Riya", "Rohan", "Sakshi", "Shreya", "Siddharth", "Tanvi", "Varun",
        "Vikram", "Zara", "Neha", "Kunal", "Divya", "Harsh", "Pooja",
        "Akash", "Simran", "Karan", "Nisha", "Raj", "Swati", "Manish",
        "Anjali", "Vivek", "Sneha", "Aditya", "Ritika",
    ]
    last_names = [
        "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Reddy", "Joshi",
        "Verma", "Mishra", "Agarwal", "Kapoor", "Malhotra", "Chauhan",
        "Nair", "Das", "Mehta", "Shah", "Rao", "Iyer", "Bhat",
        "Desai", "Pillai", "Menon", "Chopra", "Banerjee",
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def _generate_students(cursor, count=2000):
    """Generate *count* student records."""
    print(f"  Generating {count} students...")
    students = []
    for i in range(1, count + 1):
        name = _random_name()
        email = f"{name.lower().replace(' ', '.')}_{i}@university.edu"
        dept_id = random.randint(1, 10)
        year = random.randint(2018, 2025)
        gpa = round(random.uniform(2.0, 4.0), 2)
        students.append((name, email, dept_id, year, gpa))
    cursor.executemany(
        "INSERT INTO Students (name, email, department_id, enrollment_year, gpa) "
        "VALUES (?, ?, ?, ?, ?)",
        students,
    )


def _generate_enrollments(cursor, count=8000):
    """Generate *count* enrollment records."""
    print(f"  Generating {count} enrollments...")
    semesters = ["Fall 2022", "Spring 2023", "Fall 2023", "Spring 2024", "Fall 2024"]
    grades = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F", None]
    enrollments = []
    for _ in range(count):
        sid = random.randint(1, 2000)
        cid = random.randint(1, 50)
        sem = random.choice(semesters)
        grade = random.choice(grades)
        enrollments.append((sid, cid, sem, grade))
    cursor.executemany(
        "INSERT INTO Enrollments (student_id, course_id, semester, grade) "
        "VALUES (?, ?, ?, ?)",
        enrollments,
    )


def _generate_marks(cursor, count=8000):
    """Generate *count* marks records."""
    print(f"  Generating {count} marks...")
    marks = []
    for _ in range(count):
        sid = random.randint(1, 2000)
        cid = random.randint(1, 50)
        assignment = round(random.uniform(30, 100), 1)
        midterm = round(random.uniform(20, 100), 1)
        final = round(random.uniform(25, 100), 1)
        total = round((assignment * 0.3 + midterm * 0.3 + final * 0.4), 1)
        marks.append((sid, cid, assignment, midterm, final, total))
    cursor.executemany(
        "INSERT INTO Marks (student_id, course_id, assignment_score, "
        "midterm_score, final_score, total_score) VALUES (?, ?, ?, ?, ?, ?)",
        marks,
    )


def _generate_orders(cursor, count=10000):
    """Generate *count* order records."""
    print(f"  Generating {count} orders...")
    items = [
        "Notebook", "Pen Set", "Textbook", "Lab Coat", "Calculator",
        "USB Drive", "Backpack", "Headphones", "Coffee Mug", "T-Shirt",
        "Water Bottle", "Laptop Stand", "Mouse", "Keyboard", "Stationery Kit",
    ]
    base = datetime(2022, 1, 1)
    orders = []
    for _ in range(count):
        sid = random.randint(1, 2000)
        item = random.choice(items)
        qty = random.randint(1, 5)
        price = round(random.uniform(5.0, 200.0), 2)
        date = (base + timedelta(days=random.randint(0, 1000))).strftime("%Y-%m-%d")
        orders.append((sid, item, qty, price, date))
    cursor.executemany(
        "INSERT INTO Orders (student_id, item_name, quantity, price, order_date) "
        "VALUES (?, ?, ?, ?, ?)",
        orders,
    )


# ── Frontend Serving ──────────────────────────────────────────

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ── API Endpoints ─────────────────────────────────────────────

@app.route("/api/optimize", methods=["POST"])
def optimize_query():
    """
    Main endpoint: accepts a SQL query, applies heuristic optimization,
    runs execution plan analysis, and returns full comparison results.
    """
    data = request.get_json()
    sql = data.get("query", "").strip()

    if not sql:
        return jsonify({"error": "No query provided"}), 400

    # Validate: only SELECT queries allowed
    if not sql.upper().startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries are supported"}), 400

    opt_type = data.get("type", "heuristic")

    try:
        # Step 1: Optimization based on type
        conn = get_db()
        if opt_type == "cost":
            optimizer = CostBasedOptimizer(db_connection=conn, db_path=DB_PATH)
        else:
            optimizer = HeuristicOptimizer(db_connection=conn)
            
        optimized_sql, steps = optimizer.optimize(sql)
        conn.close()

        # Step 2: Execution plan & cost analysis
        analyzer = ExecutionPlanAnalyzer(DB_PATH)
        comparison = analyzer.compare_queries(sql, optimized_sql)

        return jsonify({
            "original_query": sql,
            "optimized_query": optimized_sql,
            "optimization_steps": steps,
            "comparison": comparison,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/explain", methods=["POST"])
def explain_query():
    """Return the execution plan for a single query."""
    data = request.get_json()
    sql = data.get("query", "").strip()

    if not sql or not sql.upper().startswith("SELECT"):
        return jsonify({"error": "Provide a valid SELECT query"}), 400

    try:
        analyzer = ExecutionPlanAnalyzer(DB_PATH)
        plan = analyzer.get_execution_plan(sql)
        cost = analyzer.get_cost_metrics(sql)
        return jsonify({"plan": plan, "cost": cost})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/execute", methods=["POST"])
def execute_query():
    """Execute a query and return results (limited to 100 rows)."""
    data = request.get_json()
    sql = data.get("query", "").strip()

    if not sql or not sql.upper().startswith("SELECT"):
        return jsonify({"error": "Provide a valid SELECT query"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchmany(100)
        conn.close()

        return jsonify({
            "columns": columns,
            "rows": [list(r) for r in rows],
            "total_fetched": len(rows),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sample-queries", methods=["GET"])
def sample_queries():
    """Return a list of sample queries for testing."""
    queries = [
        {
            "name": "Redundant Conditions",
            "description": "Query with tautological 1=1 condition",
            "sql": "SELECT * FROM Students WHERE department_id = 1 AND 1=1",
        },
        {
            "name": "Multi-Table JOIN",
            "description": "JOIN query with late WHERE filtering",
            "sql": (
                "SELECT * FROM Students s "
                "JOIN Enrollments e ON s.student_id = e.student_id "
                "JOIN Courses c ON e.course_id = c.course_id "
                "WHERE s.department_id = 1"
            ),
        },
        {
            "name": "Aggregation with JOIN",
            "description": "GROUP BY with multiple JOINs and filtering",
            "sql": (
                "SELECT s.name, COUNT(e.course_id) as course_count "
                "FROM Students s "
                "JOIN Enrollments e ON s.student_id = e.student_id "
                "JOIN Courses c ON e.course_id = c.course_id "
                "WHERE c.credits > 3 "
                "GROUP BY s.name"
            ),
        },
        {
            "name": "Complex Filter with JOIN",
            "description": "Multiple single-table conditions in WHERE after JOINs",
            "sql": (
                "SELECT * FROM Students s "
                "JOIN Enrollments e ON s.student_id = e.student_id "
                "JOIN Marks m ON s.student_id = m.student_id "
                "WHERE s.department_id = 2 AND m.total_score > 80 AND s.gpa > 3.0"
            ),
        },
        {
            "name": "Order Analysis",
            "description": "JOIN with date filtering and aggregation",
            "sql": (
                "SELECT s.name, SUM(o.price * o.quantity) as total_spent "
                "FROM Students s "
                "JOIN Orders o ON s.student_id = o.student_id "
                "WHERE o.order_date > '2023-06-01' AND s.department_id = 1 "
                "GROUP BY s.name"
            ),
        },
        {
            "name": "Full Scan vs Index",
            "description": "Query that benefits from index usage analysis",
            "sql": (
                "SELECT * FROM Orders "
                "WHERE student_id = 42 AND order_date > '2023-01-01'"
            ),
        },
    ]
    return jsonify(queries)


@app.route("/api/table-info", methods=["GET"])
def table_info():
    """Return information about all tables in the database."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = []
        for (name,) in cursor.fetchall():
            cursor.execute(f"SELECT COUNT(*) FROM [{name}]")
            count = cursor.fetchone()[0]
            cursor.execute(f"PRAGMA table_info([{name}])")
            columns = [
                {"name": c[1], "type": c[2], "notnull": bool(c[3]), "pk": bool(c[5])}
                for c in cursor.fetchall()
            ]
            tables.append({"name": name, "row_count": count, "columns": columns})

        conn.close()
        return jsonify(tables)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset-db", methods=["POST"])
def reset_db():
    """Reset and re-initialize the database."""
    try:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        init_database()
        return jsonify({"message": "Database reset successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Application Entry Point ──────────────────────────────────

if __name__ == "__main__":
    os.makedirs(DB_DIR, exist_ok=True)
    init_database()
    print("\n" + "=" * 55)
    print("  SQL Query Optimization System")
    print("  Open http://127.0.0.1:5000 in your browser")
    print("=" * 55 + "\n")
    app.run(debug=True, port=5000)
