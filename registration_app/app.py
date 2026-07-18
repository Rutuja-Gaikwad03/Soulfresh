"""
Registration Web Application
-----------------------------
A simple 2-page registration form app built with Flask + SQLite.

Page 1: Registration Form (/)
Page 2: Success / Preview Page (/success/<id>)

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000/
"""

import os
import re
import sqlite3
import uuid
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort, g, send_from_directory
)
from werkzeug.utils import secure_filename
from PIL import Image

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
RESUME_DIR = os.path.join(BASE_DIR, "uploads", "resumes")
PHOTO_DIR = os.path.join(BASE_DIR, "uploads", "photos")

ALLOWED_RESUME_EXT = {"pdf"}
ALLOWED_PHOTO_EXT = {"png", "jpg", "jpeg", "gif"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB total request size cap

# The WhatsApp number every registration gets sent to automatically.
# Format: country code + number, digits only, NO "+", spaces, or dashes.
# Example: India number 98765 43210 -> "919876543210"
WHATSAPP_NUMBER = "919766699515"  # <-- CHANGE THIS to the real recipient's number

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-this-in-production"  # change in production
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(RESUME_DIR, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            mobile_number TEXT NOT NULL,
            email TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            pin_code TEXT NOT NULL,
            gender TEXT NOT NULL,
            dob TEXT NOT NULL,
            education TEXT NOT NULL,
            position_applied TEXT NOT NULL,
            skills TEXT NOT NULL,
            experience TEXT,
            resume_filename TEXT NOT NULL,
            photo_filename TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS used_tokens (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Validation helpers (server-side; mirrors the client-side JS validation)
# --------------------------------------------------------------------------
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\s.'-]{1,79}$")
MOBILE_RE = re.compile(r"^\d{10}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PIN_RE = re.compile(r"^\d{6}$")

REQUIRED_FIELDS = [
    "full_name", "mobile_number", "email", "address", "city", "state",
    "pin_code", "gender", "dob", "education", "position_applied", "skills",
]


def sanitize(value):
    """Strip whitespace and remove characters that have no business being
    in plain text fields, to guard against basic injection/XSS payloads."""
    if value is None:
        return ""
    value = value.strip()
    value = re.sub(r"[<>]", "", value)
    return value


def validate_form(form):
    errors = {}
    data = {field: sanitize(form.get(field, "")) for field in REQUIRED_FIELDS}
    data["experience"] = sanitize(form.get("experience", ""))

    for field in REQUIRED_FIELDS:
        if not data[field]:
            errors[field] = "This field is required."

    if data["full_name"] and not NAME_RE.match(data["full_name"]):
        errors["full_name"] = "Full name must contain letters only (no numbers)."

    if data["mobile_number"] and not MOBILE_RE.match(data["mobile_number"]):
        errors["mobile_number"] = "Mobile number must be exactly 10 digits."

    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors["email"] = "Please enter a valid email address."

    if data["pin_code"] and not PIN_RE.match(data["pin_code"]):
        errors["pin_code"] = "PIN code must be exactly 6 digits."

    if data["gender"] not in ("Male", "Female", "Other"):
        errors["gender"] = "Please select a valid gender."

    if data["dob"]:
        try:
            dob_date = datetime.strptime(data["dob"], "%Y-%m-%d").date()
            if dob_date >= datetime.today().date():
                errors["dob"] = "Date of birth must be in the past."
        except ValueError:
            errors["dob"] = "Invalid date format."

    return data, errors


def allowed_file(filename, allowed_ext):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext


def validate_files(files):
    errors = {}
    resume = files.get("resume")
    photo = files.get("photo")

    if not resume or resume.filename == "":
        errors["resume"] = "Resume is required."
    elif not allowed_file(resume.filename, ALLOWED_RESUME_EXT):
        errors["resume"] = "Resume must be a PDF file."
    else:
        header = resume.read(5)
        resume.seek(0)
        if header != b"%PDF-":
            errors["resume"] = "Resume file does not appear to be a valid PDF."

    if not photo or photo.filename == "":
        errors["photo"] = "Profile photo is required."
    elif not allowed_file(photo.filename, ALLOWED_PHOTO_EXT):
        errors["photo"] = "Profile photo must be an image (png, jpg, jpeg, gif)."
    else:
        try:
            img = Image.open(photo)
            img.verify()
            photo.seek(0)
        except Exception:
            errors["photo"] = "Uploaded profile photo is not a valid image."

    return errors


def save_upload(file_storage, directory, prefix):
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"{prefix}_{uuid.uuid4().hex}.{ext}")
    path = os.path.join(directory, filename)
    file_storage.save(path)
    return filename


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/uploads/resumes/<path:filename>")
def serve_resume(filename):
    return send_from_directory(RESUME_DIR, filename)


@app.route("/uploads/photos/<path:filename>")
def serve_photo(filename):
    return send_from_directory(PHOTO_DIR, filename)


@app.route("/", methods=["GET"])
def register_form():
    token = uuid.uuid4().hex
    session["form_token"] = token
    return render_template("register.html", errors={}, form={}, token=token)


@app.route("/register", methods=["POST"])
def register_submit():
    # one-time form token
    submitted_token = request.form.get("form_token", "")
    session_token = session.get("form_token")

    db = get_db()
    already_used = db.execute(
        "SELECT 1 FROM used_tokens WHERE token = ?", (submitted_token,)
    ).fetchone()

    if not submitted_token or submitted_token != session_token or already_used:
        flash("This form has already been submitted, or your session expired. "
              "Please fill the form again.", "error")
        return redirect(url_for("register_form"))

    data, errors = validate_form(request.form)
    file_errors = validate_files(request.files)
    errors.update(file_errors)

    if errors:
        new_token = uuid.uuid4().hex
        session["form_token"] = new_token
        return render_template(
            "register.html", errors=errors, form=data, token=new_token
        ), 400

    # uploads save
    resume_filename = save_upload(request.files["resume"], RESUME_DIR, "resume")
    photo_filename = save_upload(request.files["photo"], PHOTO_DIR, "photo")

    # token used
    now = datetime.utcnow().isoformat()
    db.execute("INSERT INTO used_tokens (token, created_at) VALUES (?, ?)",
               (submitted_token, now))
    cur = db.execute(
        """
        INSERT INTO registrations (
            full_name, mobile_number, email, address, city, state, pin_code,
            gender, dob, education, position_applied, skills, experience,
            resume_filename, photo_filename, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["full_name"], data["mobile_number"], data["email"],
            data["address"], data["city"], data["state"], data["pin_code"],
            data["gender"], data["dob"], data["education"],
            data["position_applied"], data["skills"], data["experience"],
            resume_filename, photo_filename, now,
        ),
    )
    db.commit()
    new_id = cur.lastrowid
    session.pop("form_token", None)

    return redirect(url_for("success_page", reg_id=new_id))


@app.route("/success/<int:reg_id>", methods=["GET"])
def success_page(reg_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM registrations WHERE id = ?", (reg_id,)
    ).fetchone()
    if row is None:
        abort(404)

    whatsapp_message = build_whatsapp_message(row)
    return render_template(
        "success.html", reg=row, whatsapp_text=whatsapp_message,
        whatsapp_number=WHATSAPP_NUMBER
    )


@app.route("/edit/<int:reg_id>", methods=["GET"])
def edit_form(reg_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM registrations WHERE id = ?", (reg_id,)
    ).fetchone()
    if row is None:
        abort(404)

    token = uuid.uuid4().hex
    session["form_token"] = token
    form_data = dict(row)
    return render_template(
        "register.html", errors={}, form=form_data, token=token,
        edit_id=reg_id
    )


@app.route("/update/<int:reg_id>", methods=["POST"])
def update_submit(reg_id):
    db = get_db()
    existing = db.execute(
        "SELECT * FROM registrations WHERE id = ?", (reg_id,)
    ).fetchone()
    if existing is None:
        abort(404)

    submitted_token = request.form.get("form_token", "")
    session_token = session.get("form_token")
    already_used = db.execute(
        "SELECT 1 FROM used_tokens WHERE token = ?", (submitted_token,)
    ).fetchone()

    if not submitted_token or submitted_token != session_token or already_used:
        flash("This form has already been submitted, or your session expired.",
              "error")
        return redirect(url_for("edit_form", reg_id=reg_id))

    data, errors = validate_form(request.form)

    # replace only if files are updated
    resume_file = request.files.get("resume")
    photo_file = request.files.get("photo")
    file_errors = {}

    if resume_file and resume_file.filename:
        file_errors.update(validate_files({"resume": resume_file, "photo": photo_file or existing}))
    if photo_file and photo_file.filename and "photo" not in file_errors:
        tmp_errors = validate_files({"resume": resume_file or existing, "photo": photo_file})
        if "photo" in tmp_errors:
            file_errors["photo"] = tmp_errors["photo"]

    errors.update(file_errors)

    if errors:
        new_token = uuid.uuid4().hex
        session["form_token"] = new_token
        return render_template(
            "register.html", errors=errors, form=data, token=new_token,
            edit_id=reg_id
        ), 400

    resume_filename = existing["resume_filename"]
    photo_filename = existing["photo_filename"]
    if resume_file and resume_file.filename:
        resume_filename = save_upload(resume_file, RESUME_DIR, "resume")
    if photo_file and photo_file.filename:
        photo_filename = save_upload(photo_file, PHOTO_DIR, "photo")

    now = datetime.utcnow().isoformat()
    db.execute("INSERT INTO used_tokens (token, created_at) VALUES (?, ?)",
               (submitted_token, now))
    db.execute(
        """
        UPDATE registrations SET
            full_name=?, mobile_number=?, email=?, address=?, city=?, state=?,
            pin_code=?, gender=?, dob=?, education=?, position_applied=?,
            skills=?, experience=?, resume_filename=?, photo_filename=?
        WHERE id=?
        """,
        (
            data["full_name"], data["mobile_number"], data["email"],
            data["address"], data["city"], data["state"], data["pin_code"],
            data["gender"], data["dob"], data["education"],
            data["position_applied"], data["skills"], data["experience"],
            resume_filename, photo_filename, reg_id,
        ),
    )
    db.commit()
    session.pop("form_token", None)
    return redirect(url_for("success_page", reg_id=reg_id))


def build_whatsapp_message(row):
    """Build a complete, neatly formatted WhatsApp message containing every
    field that was collected on the registration form."""
    resume_link = url_for("serve_resume", filename=row["resume_filename"], _external=True)
    photo_link = url_for("serve_photo", filename=row["photo_filename"], _external=True)

    lines = [
        "*NEW CANDIDATE REGISTRATION*",
        "————————————————————",
        "",
        "*Personal Details*",
        f"Full Name: {row['full_name']}",
        f"Mobile: {row['mobile_number']}",
        f"Email: {row['email']}",
        f"Gender: {row['gender']}",
        f"Date of Birth: {row['dob']}",
        "",
        "*Address*",
        f"{row['address']}",
        f"{row['city']}, {row['state']} - {row['pin_code']}",
        "",
        "*Application Details*",
        f"Position Applied For: {row['position_applied']}",
        f"Education: {row['education']}",
        f"Skills: {row['skills']}",
        f"Experience: {row['experience'] or 'N/A'}",
        "",
        "*Uploaded Files*",
        f"Resume (PDF): {resume_link}",
        f"Profile Photo: {photo_link}",
        "",
        "————————————————————",
        f"Registration ID: #{row['id']}",
        f"Submitted: {row['created_at']}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
else:
    init_db()
