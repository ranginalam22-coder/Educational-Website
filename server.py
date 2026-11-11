#!/usr/bin/env python3
"""Evergreen University website and SQLite admissions service."""

import argparse
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timezone
from getpass import getpass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("EVERGREEN_DB", ROOT / "university.sqlite3"))
HOST = os.environ.get("EVERGREEN_HOST", "127.0.0.1")
PORT = int(os.environ.get("EVERGREEN_PORT", "8000"))
SESSION_TTL = 60 * 60 * 24 * 14
PASSWORD_ITERATIONS = 600_000
SESSION_COOKIE = "evergreen_session"
ADMISSION_STATUSES = ("Under review", "Additional information needed", "Accepted", "Not accepted")
FACULTIES = (
    {
        "slug": "engineering",
        "name": "Faculty of Engineering",
        "shortName": "Engineering",
        "intro": "Design, build, and sustain the systems and infrastructure that move our world forward.",
        "requirements": ["High school diploma or equivalent", "Mathematics and physics preparation", "Official academic transcripts", "Personal statement describing your interest in engineering"],
        "programs": [
            ("civil-engineering", "Civil Engineering", "4 years", "Plan resilient cities and infrastructure. Study structural analysis, geotechnics, transport, water systems, and sustainable construction.", "Prepare to shape the built environment through practical design and engineering principles."),
            ("electrical-engineering", "Electrical Engineering", "4 years", "Explore electronics, power systems, communications, control systems, and embedded technology through hands-on laboratory work.", "Build expertise in the electrical systems that connect and power modern life."),
            ("mechanical-engineering", "Mechanical Engineering", "4 years", "Learn thermodynamics, materials, machine design, manufacturing, robotics, and computer-aided engineering.", "Turn ideas into efficient machines and products, from concept through manufacture."),
        ],
    },
    {
        "slug": "computer-science",
        "name": "Faculty of Computer Science",
        "shortName": "Computer Science",
        "intro": "Understand the technology behind the future and create thoughtful solutions for real people.",
        "requirements": ["High school diploma or equivalent", "Mathematics preparation recommended", "Official academic transcripts", "Personal statement describing your interest in computing"],
        "programs": [
            ("software-engineering", "Software Engineering", "4 years", "Design dependable software using programming, architecture, testing, cloud computing, and collaborative development practices.", "Build useful, reliable software and learn how professional engineering teams deliver it."),
            ("information-technology", "Information Technology", "4 years", "Study networks, cloud services, cybersecurity foundations, systems administration, and the technology organizations depend on.", "Develop practical skills to support and improve modern digital infrastructure."),
            ("computer-science", "Computer Science", "4 years", "Explore algorithms, programming languages, data, artificial intelligence, operating systems, and the theory behind computation.", "Gain a broad foundation for solving complex problems with computing."),
        ],
    },
    {
        "slug": "business-administration",
        "name": "Faculty of Business Administration (BBA)",
        "shortName": "Business Administration",
        "intro": "Learn to lead organizations with sound judgment, analytical thinking, and a global perspective.",
        "requirements": ["High school diploma or equivalent", "Official academic transcripts", "Personal statement describing your academic and career goals", "English language proficiency documentation where applicable"],
        "programs": [
            ("business-management", "Business Management", "4 years", "Study strategy, leadership, operations, entrepreneurship, and organizational behavior through real-world business cases.", "Develop the knowledge to manage teams, organizations, and new ventures."),
            ("finance", "Finance", "4 years", "Explore financial markets, corporate finance, investment analysis, accounting, and responsible financial decision-making.", "Learn how individuals and organizations make informed financial decisions."),
            ("marketing", "Marketing", "4 years", "Combine consumer insights, brand strategy, digital channels, research, and creative campaigns to understand modern markets.", "Create relevant, research-informed marketing that connects organizations with people."),
            ("human-resource-management", "Human Resource Management", "4 years", "Learn talent development, employment relations, inclusive workplaces, people analytics, and strategic human resources.", "Help organizations build supportive workplaces where people can thrive."),
        ],
    },
    {
        "slug": "law",
        "name": "Faculty of Law",
        "shortName": "Law",
        "intro": "Examine the principles, institutions, and advocacy that help build a just and orderly society.",
        "requirements": ["High school diploma or equivalent", "Official academic transcripts", "Personal statement outlining your motivation to study law", "English language proficiency documentation where applicable"],
        "programs": [
            ("business-law", "Business Law", "4 years", "Study contracts, commercial organizations, corporate governance, transactions, and the legal frameworks of business.", "Understand the legal foundations that guide responsible commercial activity."),
            ("criminal-law", "Criminal Law", "4 years", "Examine criminal responsibility, evidence, procedure, justice systems, and the principles that protect due process.", "Explore how criminal law and justice institutions serve individuals and communities."),
            ("international-law", "International Law", "4 years", "Study public international law, human rights, treaties, international institutions, and cross-border legal questions.", "Build a foundation for analyzing legal issues across nations and institutions."),
            ("civil-law", "Civil Law", "4 years", "Explore private law, obligations, property, civil procedure, dispute resolution, and access to justice.", "Understand the rules and remedies that shape relationships between people and organizations."),
        ],
    },
)


def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def initialize_database():
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                password_salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'admin')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS faculties (
                id INTEGER PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                short_name TEXT NOT NULL,
                intro TEXT NOT NULL,
                requirements_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS programs (
                id INTEGER PRIMARY KEY,
                faculty_id INTEGER NOT NULL REFERENCES faculties(id),
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                duration TEXT NOT NULL,
                description TEXT NOT NULL,
                outcomes TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY,
                reference TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                faculty_id INTEGER NOT NULL REFERENCES faculties(id),
                program_id INTEGER NOT NULL REFERENCES programs(id),
                date_of_birth TEXT NOT NULL,
                country TEXT NOT NULL,
                address TEXT NOT NULL,
                education TEXT NOT NULL,
                school TEXT NOT NULL,
                start_term TEXT NOT NULL,
                statement TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Under review',
                submitted_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                csrf_token TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS applications_user_id_idx ON applications(user_id);
            CREATE INDEX IF NOT EXISTS applications_submitted_at_idx ON applications(submitted_at);
            CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);
            """
        )
        for faculty in FACULTIES:
            db.execute(
                """INSERT INTO faculties (slug, name, short_name, intro, requirements_json)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(slug) DO UPDATE SET name=excluded.name, short_name=excluded.short_name,
                   intro=excluded.intro, requirements_json=excluded.requirements_json""",
                (faculty["slug"], faculty["name"], faculty["shortName"], faculty["intro"], json.dumps(faculty["requirements"])),
            )
            faculty_id = db.execute("SELECT id FROM faculties WHERE slug = ?", (faculty["slug"],)).fetchone()["id"]
            for slug, name, duration, description, outcomes in faculty["programs"]:
                db.execute(
                    """INSERT INTO programs (faculty_id, slug, name, duration, description, outcomes)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(slug) DO UPDATE SET faculty_id=excluded.faculty_id, name=excluded.name,
                       duration=excluded.duration, description=excluded.description, outcomes=excluded.outcomes""",
                    (faculty_id, slug, name, duration, description, outcomes),
                )


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return salt, digest


def create_admin(email):
    email = email.strip().lower()
    if "@" not in email or len(email) > 254:
        raise ValueError("Provide a valid administrator email address.")
    password = getpass("New administrator password (at least 12 characters): ")
    confirmation = getpass("Confirm administrator password: ")
    if password != confirmation:
        raise ValueError("The passwords did not match.")
    if len(password) < 12:
        raise ValueError("Administrator passwords must be at least 12 characters.")
    salt, digest = hash_password(password)
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute(
            """INSERT INTO users (email, first_name, last_name, password_salt, password_hash, role, created_at)
               VALUES (?, 'University', 'Administrator', ?, ?, 'admin', ?)""",
            (email, salt, digest, now),
        )
    print(f"Administrator account created for {email}.")


def public_user(row):
    return {
        "email": row["email"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "phone": row["phone"],
        "role": row["role"],
    }


class UniversityHandler(BaseHTTPRequestHandler):
    server_version = "EvergreenUniversity/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' https://images.unsplash.com data:; script-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        if headers:
            for key, value in headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, message):
        self.send_json(status, {"error": message})

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid request size.") from exc
        if length < 1 or length > 1_000_000:
            raise ValueError("Request body must be between 1 byte and 1 MB.")
        try:
            value = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Request body must contain valid JSON.") from exc
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object.")
        return value

    def session_context(self, db, create=False):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        token = morsel.value if morsel else ""
        row = None
        if token and len(token) == 64:
            row = db.execute(
                """SELECT sessions.csrf_token, sessions.expires_at, users.*
                   FROM sessions LEFT JOIN users ON sessions.user_id = users.id
                   WHERE sessions.token_hash = ?""",
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
            if row and row["expires_at"] <= int(time.time()):
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
                row = None
        if row:
            return token, row["csrf_token"], row if row["email"] else None, []
        if not create:
            return None, None, None, []
        new_token = secrets.token_hex(32)
        csrf = secrets.token_urlsafe(32)
        expires = int(time.time()) + SESSION_TTL
        db.execute(
            "INSERT INTO sessions (token_hash, csrf_token, expires_at) VALUES (?, ?, ?)",
            (hashlib.sha256(new_token.encode()).hexdigest(), csrf, expires),
        )
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
        cookie_header = (("Set-Cookie", f"{SESSION_COOKIE}={new_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}{secure}"),)
        return new_token, csrf, None, cookie_header

    def require_csrf(self, expected):
        supplied = self.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            self.send_error_json(HTTPStatus.FORBIDDEN, "Your session has expired. Refresh the page and try again.")
            return False
        return True

    def require_user(self, user, role=None):
        if not user:
            self.send_error_json(HTTPStatus.UNAUTHORIZED, "Please log in to continue.")
            return False
        if role and user["role"] != role:
            self.send_error_json(HTTPStatus.FORBIDDEN, "Administrator access is required.")
            return False
        return True

    def api_get(self, path, db):
        if path == "/api/catalog":
            faculties = []
            for row in db.execute("SELECT * FROM faculties ORDER BY id"):
                programs = [
                    {"slug": program["slug"], "name": program["name"], "duration": program["duration"],
                     "description": program["description"], "outcomes": program["outcomes"]}
                    for program in db.execute("SELECT * FROM programs WHERE faculty_id = ? ORDER BY id", (row["id"],))
                ]
                faculties.append({
                    "slug": row["slug"], "name": row["name"], "shortName": row["short_name"],
                    "intro": row["intro"], "requirements": json.loads(row["requirements_json"]), "programs": programs,
                })
            self.send_json(HTTPStatus.OK, {"faculties": faculties})
            return

        if path == "/api/session":
            _, csrf, user, headers = self.session_context(db, create=True)
            self.send_json(HTTPStatus.OK, {"csrfToken": csrf, "user": public_user(user) if user else None}, headers)
            return

        _, _, user, _ = self.session_context(db)
        if path == "/api/applications":
            if not self.require_user(user):
                return
            applications = db.execute(
                """SELECT applications.reference, applications.status, applications.submitted_at,
                          faculties.name AS faculty, programs.name AS program
                   FROM applications JOIN faculties ON applications.faculty_id = faculties.id
                   JOIN programs ON applications.program_id = programs.id
                   WHERE applications.user_id = ? ORDER BY applications.submitted_at DESC""",
                (user["id"],),
            ).fetchall()
            self.send_json(HTTPStatus.OK, {"applications": [
                {"reference": row["reference"], "status": row["status"], "submittedAt": row["submitted_at"],
                 "faculty": row["faculty"], "program": row["program"]}
                for row in applications
            ]})
            return

        if path == "/api/admin/applications":
            if not self.require_user(user, "admin"):
                return
            rows = db.execute(
                """SELECT applications.reference, applications.status, applications.submitted_at,
                          applications.updated_at, applications.date_of_birth, applications.country,
                          applications.address, applications.education, applications.school,
                          applications.start_term, applications.statement, users.email, users.first_name,
                          users.last_name, users.phone, faculties.name AS faculty, programs.name AS program
                   FROM applications JOIN users ON applications.user_id = users.id
                   JOIN faculties ON applications.faculty_id = faculties.id
                   JOIN programs ON applications.program_id = programs.id
                   ORDER BY applications.submitted_at DESC"""
            ).fetchall()
            self.send_json(HTTPStatus.OK, {"applications": [dict(row) for row in rows]})
            return

        if path == "/api/admin/students":
            if not self.require_user(user, "admin"):
                return
            rows = db.execute(
                """SELECT users.email, users.first_name, users.last_name, users.phone, users.created_at,
                          COUNT(applications.id) AS application_count
                   FROM users LEFT JOIN applications ON applications.user_id = users.id
                   WHERE users.role = 'student' GROUP BY users.id ORDER BY users.created_at DESC"""
            ).fetchall()
            self.send_json(HTTPStatus.OK, {"students": [dict(row) for row in rows]})
            return

        self.send_error_json(HTTPStatus.NOT_FOUND, "API endpoint not found.")

    def api_post(self, path, db):
        try:
            data = self.read_json()
        except ValueError as error:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(error))
            return

        _, csrf, user, _ = self.session_context(db, create=True)
        if not self.require_csrf(csrf):
            return

        if path == "/api/register":
            required = ("firstName", "lastName", "email", "password")
            if any(not isinstance(data.get(key), str) or not data[key].strip() for key in required):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Complete all required fields.")
                return
            first_name, last_name = data["firstName"].strip(), data["lastName"].strip()
            email = data["email"].strip().lower()
            password = data["password"]
            if len(first_name) > 60 or len(last_name) > 60 or len(email) > 254 or "@" not in email:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Check your name and email address.")
                return
            if len(password) < 10 or len(password) > 256:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Your password must be between 10 and 256 characters.")
                return
            salt, digest = hash_password(password)
            try:
                cursor = db.execute(
                    """INSERT INTO users (email, first_name, last_name, password_salt, password_hash, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (email, first_name, last_name, salt, digest, datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError:
                self.send_error_json(HTTPStatus.CONFLICT, "An account with that email already exists. Please log in.")
                return
            self.create_authenticated_session(db, cursor.lastrowid)
            return

        if path == "/api/login":
            email, password = data.get("email"), data.get("password")
            if not isinstance(email, str) or not isinstance(password, str):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Enter your email and password.")
                return
            account = db.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)).fetchone()
            salt = account["password_salt"] if account else b"\0" * 16
            expected = account["password_hash"] if account else b"\0" * 32
            actual = hash_password(password, salt)[1]
            if not hmac.compare_digest(expected, actual) or not account:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "Email or password is incorrect.")
                return
            self.create_authenticated_session(db, account["id"])
            return

        if path == "/api/logout":
            if not csrf:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "Your session has expired.")
                return
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            morsel = cookie.get(SESSION_COOKIE)
            if morsel:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(morsel.value.encode()).hexdigest(),))
            self.send_json(HTTPStatus.OK, {"ok": True}, (("Set-Cookie", f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"),))
            return

        if path == "/api/profile":
            if not self.require_user(user) or not self.require_csrf(csrf):
                return
            first_name, last_name, phone = data.get("firstName"), data.get("lastName"), data.get("phone", "")
            if not all(isinstance(value, str) for value in (first_name, last_name, phone)):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Enter valid profile information.")
                return
            first_name, last_name, phone = first_name.strip(), last_name.strip(), phone.strip()
            if not first_name or not last_name or len(first_name) > 60 or len(last_name) > 60 or len(phone) > 30:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Check the name and phone number fields.")
                return
            db.execute("UPDATE users SET first_name = ?, last_name = ?, phone = ? WHERE id = ?", (first_name, last_name, phone, user["id"]))
            self.send_json(HTTPStatus.OK, {"user": public_user(db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone())})
            return

        if path == "/api/admissions":
            if not self.require_user(user, "student") or not self.require_csrf(csrf):
                return
            string_fields = ("phone", "dateOfBirth", "country", "address", "education", "school", "faculty", "program", "startTerm")
            if any(not isinstance(data.get(key), str) or not data[key].strip() for key in string_fields):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Complete all required admission fields.")
                return
            faculty = db.execute("SELECT * FROM faculties WHERE slug = ?", (data["faculty"],)).fetchone()
            program = db.execute("SELECT * FROM programs WHERE slug = ?", (data["program"],)).fetchone()
            if not faculty or not program or program["faculty_id"] != faculty["id"]:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Choose an available program from the selected faculty.")
                return
            if data.get("consent") is not True:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Please confirm your information before submitting.")
                return
            limits = {"phone": 30, "dateOfBirth": 10, "country": 80, "address": 200, "education": 80, "school": 120, "startTerm": 80}
            if any(len(data[key].strip()) > limit for key, limit in limits.items()):
                self.send_error_json(HTTPStatus.BAD_REQUEST, "One or more fields exceed the allowed length.")
                return
            if not isinstance(data.get("statement", ""), str) or len(data.get("statement", "")) > 800:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Your statement must be 800 characters or fewer.")
                return
            try:
                date_of_birth = datetime.strptime(data["dateOfBirth"], "%Y-%m-%d").date()
            except ValueError:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Enter a valid date of birth.")
                return
            if date_of_birth >= datetime.now(timezone.utc).date():
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Date of birth must be in the past.")
                return
            reference = "EU-" + secrets.token_hex(5).upper()
            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                """INSERT INTO applications
                   (reference, user_id, faculty_id, program_id, date_of_birth, country, address, education,
                    school, start_term, statement, submitted_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (reference, user["id"], faculty["id"], program["id"], data["dateOfBirth"], data["country"].strip(),
                 data["address"].strip(), data["education"].strip(), data["school"].strip(), data["startTerm"].strip(),
                 data.get("statement", "").strip(), now, now),
            )
            db.execute("UPDATE users SET phone = ? WHERE id = ?", (data["phone"].strip(), user["id"]))
            self.send_json(HTTPStatus.CREATED, {"reference": reference, "status": "Under review"})
            return

        if path == "/api/admin/status":
            if not self.require_user(user, "admin") or not self.require_csrf(csrf):
                return
            reference, status = data.get("reference"), data.get("status")
            if not isinstance(reference, str) or status not in ADMISSION_STATUSES:
                self.send_error_json(HTTPStatus.BAD_REQUEST, "Choose a valid application status.")
                return
            result = db.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE reference = ?",
                (status, datetime.now(timezone.utc).isoformat(), reference),
            )
            if result.rowcount == 0:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Application not found.")
                return
            self.send_json(HTTPStatus.OK, {"ok": True})
            return

        self.send_error_json(HTTPStatus.NOT_FOUND, "API endpoint not found.")

    def create_authenticated_session(self, db, user_id):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        old = cookie.get(SESSION_COOKIE)
        if old:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(old.value.encode()).hexdigest(),))
        token, csrf = secrets.token_hex(32), secrets.token_urlsafe(32)
        expires = int(time.time()) + SESSION_TTL
        db.execute(
            "INSERT INTO sessions (token_hash, csrf_token, user_id, expires_at) VALUES (?, ?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), csrf, user_id, expires),
        )
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
        account = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        self.send_json(
            HTTPStatus.OK,
            {"user": public_user(account), "csrfToken": csrf},
            (("Set-Cookie", f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}{secure}"),),
        )

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path.startswith("/api/"):
            try:
                with connect() as db:
                    self.api_get(path, db)
            except (sqlite3.Error, ValueError) as error:
                print(f"Database/API error: {error}", file=sys.stderr)
                self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "The request could not be completed. Please try again.")
            return
        if path in ("/admin-export.csv", "/admin-students.csv"):
            self.export_csv(students_only=path == "/admin-students.csv")
            return
        self.serve_static(path)

    def do_POST(self):
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint not found.")
            return
        try:
            with connect() as db:
                self.api_post(path, db)
        except sqlite3.IntegrityError as error:
            print(f"Database constraint error: {error}", file=sys.stderr)
            self.send_error_json(HTTPStatus.CONFLICT, "This information conflicts with an existing record.")
        except (sqlite3.Error, OSError, ValueError) as error:
            print(f"Database/API error: {error}", file=sys.stderr)
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "The request could not be completed. Please try again.")

    def export_csv(self, students_only=False):
        with connect() as db:
            _, _, user, _ = self.session_context(db)
            if not user:
                self.send_error(HTTPStatus.UNAUTHORIZED, "Log in as an administrator to export applications.")
                return
            if user["role"] != "admin":
                self.send_error(HTTPStatus.FORBIDDEN, "Administrator access is required.")
                return
            if students_only:
                rows = db.execute(
                    """SELECT users.first_name, users.last_name, users.email, users.phone, users.created_at,
                              COUNT(applications.id) AS application_count
                       FROM users LEFT JOIN applications ON applications.user_id = users.id
                       WHERE users.role = 'student' GROUP BY users.id ORDER BY users.created_at DESC"""
                ).fetchall()
                headers = ["First Name", "Last Name", "Email", "Phone", "Account Created", "Application Count"]
                filename = "university-students.csv"
            else:
                rows = db.execute(
                    """SELECT applications.reference, applications.status, applications.submitted_at,
                              applications.updated_at, users.first_name, users.last_name, users.email, users.phone,
                              faculties.name AS faculty, programs.name AS program, applications.date_of_birth,
                              applications.country, applications.address, applications.education, applications.school,
                              applications.start_term, applications.statement
                       FROM applications JOIN users ON applications.user_id = users.id
                       JOIN faculties ON applications.faculty_id = faculties.id
                       JOIN programs ON applications.program_id = programs.id ORDER BY applications.submitted_at DESC"""
                ).fetchall()
                headers = ["Reference", "Status", "Submitted At", "Updated At", "First Name", "Last Name", "Email",
                           "Phone", "Faculty", "Program", "Date of Birth", "Country", "Address", "Education",
                           "School", "Preferred Start", "Applicant Statement"]
                filename = "university-applications.csv"
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([self.safe_csv_value(value) for value in row])
        body = ("\ufeff" + output.getvalue()).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def safe_csv_value(value):
        if value is None:
            return ""
        text = str(value)
        if text.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    def serve_static(self, path):
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        requested = (ROOT / relative).resolve()
        if ROOT not in requested.parents or not requested.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Page not found.")
            return
        if requested.suffix not in (".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico"):
            self.send_error(HTTPStatus.FORBIDDEN, "File type not served.")
            return
        content = requested.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".ico": "image/x-icon",
        }.get(requested.suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' https://images.unsplash.com data:; script-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)


def main():
    parser = argparse.ArgumentParser(description="Run Evergreen University website.")
    parser.add_argument("--create-admin", metavar="EMAIL", help="Create the first (or an additional) administrator.")
    args = parser.parse_args()
    initialize_database()
    if args.create_admin:
        try:
            create_admin(args.create_admin)
        except (ValueError, sqlite3.IntegrityError) as error:
            parser.error(str(error))
        return
    server = ThreadingHTTPServer((HOST, PORT), UniversityHandler)
    print(f"Evergreen University running at http://{HOST}:{PORT}/")
    print(f"SQLite database: {DATABASE}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
