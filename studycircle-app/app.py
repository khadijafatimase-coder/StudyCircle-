
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "studycircle-prototype-change-this-key"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "studycircle.db"


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS groups_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memberships (
                user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                UNIQUE(user_id, group_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(group_id) REFERENCES groups_table(id)
            );

            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                url TEXT NOT NULL
            );
        """)

        if db.execute("SELECT COUNT(*) FROM groups_table").fetchone()[0] == 0:
            db.executemany("""
                INSERT INTO groups_table (name, subject, description)
                VALUES (?, ?, ?)
            """, [
                ("Python Learners", "Programming",
                 "Learn Python fundamentals and practice coding together."),
                ("Web Development Club", "Web Development",
                 "Explore HTML, CSS, JavaScript and Flask."),
                ("AI Study Group", "Artificial Intelligence",
                 "Discuss AI concepts, search algorithms and intelligent agents."),
                ("Database Learners", "Database",
                 "Practice SQL, tables, queries and database design.")
            ])

        if db.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0:
            db.executemany("""
                INSERT INTO resources (title, category, description, url)
                VALUES (?, ?, ?, ?)
            """, [
                ("HTML Basics", "Web Development",
                 "Learn the structure of web pages.",
                 "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Structuring_content"),
                ("CSS Fundamentals", "Web Development",
                 "Learn layouts, colors and responsive styling.",
                 "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Styling_basics"),
                ("Python Tutorial", "Programming",
                 "Explore Python syntax and programming concepts.",
                 "https://docs.python.org/3/tutorial/"),
                ("SQL Tutorial", "Database",
                 "Learn relational databases and SQL queries.",
                 "https://www.w3schools.com/sql/"),
                ("AI Search Algorithms", "Artificial Intelligence",
                 "Review search strategies used in AI.",
                 "https://www.ibm.com/think/topics/artificial-intelligence")
            ])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access that page.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in every field.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")
            return render_template("register.html")

        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password))
                )
            flash("Account created! You can now log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as db:
        groups = db.execute("""
            SELECT g.*, 
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = g.id AND m.user_id = ?
            ) AS joined
            FROM groups_table g
            ORDER BY g.name
        """, (session["user_id"],)).fetchall()

        resources = db.execute(
            "SELECT * FROM resources ORDER BY title LIMIT 3"
        ).fetchall()

        joined_count = db.execute(
            "SELECT COUNT(*) FROM memberships WHERE user_id = ?",
            (session["user_id"],)
        ).fetchone()[0]

    return render_template(
        "dashboard.html",
        groups=groups,
        resources=resources,
        joined_count=joined_count
    )


@app.route("/groups")
@login_required
def groups():
    search = request.args.get("q", "").strip()

    with get_db() as db:
        results = db.execute("""
            SELECT g.*,
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.group_id = g.id AND m.user_id = ?
            ) AS joined
            FROM groups_table g
            WHERE g.name LIKE ? OR g.subject LIKE ?
               OR g.description LIKE ?
            ORDER BY g.name
        """, (
            session["user_id"],
            f"%{search}%", f"%{search}%", f"%{search}%"
        )).fetchall()

    return render_template("groups.html", groups=results, search=search)


@app.route("/join/<int:group_id>", methods=["POST"])
@login_required
def join_group(group_id):
    with get_db() as db:
        group = db.execute(
            "SELECT id FROM groups_table WHERE id = ?", (group_id,)
        ).fetchone()

        if not group:
            flash("Study group not found.", "error")
            return redirect(url_for("groups"))

        db.execute("""
            INSERT OR IGNORE INTO memberships (user_id, group_id)
            VALUES (?, ?)
        """, (session["user_id"], group_id))

    flash("You have joined the study group!", "success")
    return redirect(request.referrer or url_for("groups"))


@app.route("/resources")
@login_required
def resources():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    query = "SELECT * FROM resources WHERE title LIKE ? OR description LIKE ?"
    params = [f"%{search}%", f"%{search}%"]

    if category:
        query = """
            SELECT * FROM resources
            WHERE (title LIKE ? OR description LIKE ?) AND category = ?
        """
        params.append(category)

    with get_db() as db:
        items = db.execute(query + " ORDER BY title", params).fetchall()
        categories = db.execute(
            "SELECT DISTINCT category FROM resources ORDER BY category"
        ).fetchall()

    return render_template(
        "resources.html",
        resources=items,
        categories=categories,
        search=search,
        selected_category=category
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
