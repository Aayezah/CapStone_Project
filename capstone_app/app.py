from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "capstone_secret_key"

DATABASE = "database/app.db"
UPLOAD_IMAGE_FOLDER = "static/uploads/images"
UPLOAD_PDF_FOLDER = "static/uploads/pdfs"

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_PDF_EXTENSIONS = {"pdf"}


# ---------------- DB HELPERS ----------------

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def allowed_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PDF_EXTENSIONS


# ---------------- HOME & ABOUT ----------------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------- LOGOUT (COMMON) ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ================= USER AUTH =================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("auth/user_signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session.clear()               # IMPORTANT
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("user_dashboard"))

    return render_template("auth/user_login.html")


# ---------------- USER DASHBOARD ----------------

@app.route("/user/dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    projects = conn.execute("SELECT * FROM projects").fetchall()
    enrolled = conn.execute(
        "SELECT project_id FROM enrollments WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()

    enrolled_ids = [e["project_id"] for e in enrolled]
    conn.close()

    return render_template(
        "user/dashboard.html",
        projects=projects,
        enrolled_ids=enrolled_ids
    )


@app.route("/enroll/<int:project_id>")
def enroll_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    already = conn.execute(
        "SELECT * FROM enrollments WHERE user_id=? AND project_id=?",
        (session["user_id"], project_id)
    ).fetchone()

    if not already:
        conn.execute("""
            INSERT INTO enrollments (user_id, project_id, user_name, status, enrolled_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            project_id,
            session["user_name"],
            "enrolled",
            datetime.now()
        ))
        conn.commit()

    conn.close()
    return redirect(url_for("user_dashboard"))


@app.route("/project/<int:project_id>")
def view_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    enrolled = conn.execute(
        "SELECT * FROM enrollments WHERE user_id=? AND project_id=?",
        (session["user_id"], project_id)
    ).fetchone()

    if not enrolled:
        conn.close()
        return redirect(url_for("user_dashboard"))

    project = conn.execute(
        "SELECT * FROM projects WHERE id=?",
        (project_id,)
    ).fetchone()

    conn.close()
    return render_template("user/project_view.html", project=project)


# ================= ADMIN AUTH =================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM admins WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if admin:
            session.clear()               # IMPORTANT
            session["admin_id"] = admin["id"]
            return redirect(url_for("admin_dashboard"))

    return render_template("auth/admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    projects = conn.execute("SELECT * FROM projects").fetchall()
    conn.close()

    return render_template("admin/dashboard.html", projects=projects)


@app.route("/admin/create-project", methods=["GET", "POST"])
def create_project():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        image = request.files["image"]
        pdf = request.files["pdf"]

        if image and pdf and allowed_image(image.filename) and allowed_pdf(pdf.filename):
            image_name = secure_filename(image.filename)
            pdf_name = secure_filename(pdf.filename)

            image_path = os.path.join(UPLOAD_IMAGE_FOLDER, image_name)
            pdf_path = os.path.join(UPLOAD_PDF_FOLDER, pdf_name)

            image.save(image_path)
            pdf.save(pdf_path)

            conn = get_db_connection()
            conn.execute("""
                INSERT INTO projects (title, description, image_path, pdf_path, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                title,
                description,
                image_path,
                pdf_path,
                session["admin_id"],
                datetime.now()
            ))
            conn.commit()
            conn.close()

            return redirect(url_for("admin_dashboard"))

    return render_template("admin/create_project.html")


@app.route("/admin/enrollments/<int:project_id>")
def admin_enrollments(project_id):
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    enrollments = conn.execute(
        "SELECT user_name, enrolled_at FROM enrollments WHERE project_id=?",
        (project_id,)
    ).fetchall()
    conn.close()

    return render_template("admin/enrollments.html", enrollments=enrollments)


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    app.run(debug=True)
