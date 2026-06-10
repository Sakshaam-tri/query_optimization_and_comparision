-- ============================================================
-- SQL Query Optimization Project - Database Schema
-- Creates sample tables for demonstrating query optimization
-- ============================================================

-- Departments Table
CREATE TABLE IF NOT EXISTS Departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    building TEXT,
    budget REAL
);

-- Professors Table
CREATE TABLE IF NOT EXISTS Professors (
    professor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department_id INTEGER,
    salary REAL,
    hire_date TEXT,
    FOREIGN KEY (department_id) REFERENCES Departments(department_id)
);

-- Students Table
CREATE TABLE IF NOT EXISTS Students (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    department_id INTEGER,
    enrollment_year INTEGER,
    gpa REAL,
    FOREIGN KEY (department_id) REFERENCES Departments(department_id)
);

-- Courses Table
CREATE TABLE IF NOT EXISTS Courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    department_id INTEGER,
    credits INTEGER,
    professor_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES Departments(department_id),
    FOREIGN KEY (professor_id) REFERENCES Professors(professor_id)
);

-- Enrollments Table
CREATE TABLE IF NOT EXISTS Enrollments (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    semester TEXT,
    grade TEXT,
    FOREIGN KEY (student_id) REFERENCES Students(student_id),
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
);

-- Marks Table
CREATE TABLE IF NOT EXISTS Marks (
    mark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    course_id INTEGER,
    assignment_score REAL,
    midterm_score REAL,
    final_score REAL,
    total_score REAL,
    FOREIGN KEY (student_id) REFERENCES Students(student_id),
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
);

-- Orders Table (for additional query testing)
CREATE TABLE IF NOT EXISTS Orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    item_name TEXT,
    quantity INTEGER,
    price REAL,
    order_date TEXT,
    FOREIGN KEY (student_id) REFERENCES Students(student_id)
);

-- ============================================================
-- Indexes for performance testing
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_students_dept ON Students(department_id);
CREATE INDEX IF NOT EXISTS idx_students_year ON Students(enrollment_year);
CREATE INDEX IF NOT EXISTS idx_enrollments_student ON Enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course ON Enrollments(course_id);
CREATE INDEX IF NOT EXISTS idx_marks_student ON Marks(student_id);
CREATE INDEX IF NOT EXISTS idx_marks_course ON Marks(course_id);
CREATE INDEX IF NOT EXISTS idx_courses_dept ON Courses(department_id);
CREATE INDEX IF NOT EXISTS idx_orders_student ON Orders(student_id);
CREATE INDEX IF NOT EXISTS idx_orders_date ON Orders(order_date);
CREATE INDEX IF NOT EXISTS idx_professors_dept ON Professors(department_id);
