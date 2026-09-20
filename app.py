import hmac
import os
import secrets
from functools import wraps
from datetime import datetime

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
database_path = os.path.join(app.root_path, "studenthub.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path.replace(os.sep, '/')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app_environment = os.environ.get("STUDENTHUB_ENV", "development").lower()
is_production = app_environment == "production"
secret_key = os.environ.get("STUDENTHUB_SECRET_KEY")
if is_production and not secret_key:
    raise RuntimeError("STUDENTHUB_SECRET_KEY must be set in production.")
app.config["SECRET_KEY"] = secret_key or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=is_production,
    SESSION_COOKIE_SAMESITE="Lax",
)

db = SQLAlchemy(app)

MAX_LENGTHS = {
    "name": 100,
    "email": 120,
    "password": 256,
    "title": 200,
    "description": 2000,
    "subject": 100,
    "content": 10000,
}
ALLOWED_ASSIGNMENT_STATUSES = {"Pending", "Completed"}


def csrf_token():
    token = session.get("_csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


@app.context_processor
def inject_security_context():
    return {"csrf_token": csrf_token}


@app.before_request
def protect_state_changing_requests():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    expected_token = session.get("_csrf_token")
    provided_token = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
    if (
        not expected_token
        or not provided_token
        or not hmac.compare_digest(str(expected_token), str(provided_token))
    ):
        if request.path.startswith("/api/"):
            return jsonify(error="CSRF validation failed."), 400
        return render_template(
            "error.html",
            status_code=400,
            message="Your form could not be verified. Please refresh and try again.",
        ), 400
    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    assignments = db.relationship("Assignment", back_populates="user", cascade="all, delete-orphan")
    notes = db.relationship("Note", back_populates="user", cascade="all, delete-orphan")
    tasks = db.relationship("Task", back_populates="user", cascade="all, delete-orphan")


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    subject = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", back_populates="assignments")


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", back_populates="notes")


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", back_populates="tasks")


def migrate_ownership_columns():
    """Add required ownership columns without discarding legacy rows."""
    inspector = db.inspect(db.engine)
    ownership_columns = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in ("assignment", "note", "task")
    }
    migrated_tables = [
        table for table, columns in ownership_columns.items() if "user_id" in columns
    ]
    if len(migrated_tables) == 3:
        return
    if migrated_tables:
        raise RuntimeError(
            "StudentHub ownership migration is incomplete; "
            "assignment, note, and task must be migrated together."
        )

    legacy_user = db.session.scalar(
        db.select(User).where(User.email == "database-test@studenthub.local")
    )
    if legacy_user is None:
        legacy_user = db.session.scalar(db.select(User).order_by(User.id))
    if legacy_user is None:
        legacy_user = User(
            name="Database Migration User",
            email="database-migration@studenthub.local",
            password=generate_password_hash("development-only-migration-user"),
        )
        db.session.add(legacy_user)
        db.session.flush()
    db.session.commit()

    connection = db.engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table, columns in (
            (
                "assignment",
                "id, title, description, subject, due_date, status, user_id",
            ),
            ("note", "id, title, subject, content, created_at, user_id"),
            ("task", "id, title, description, due_date, completed, user_id"),
        ):
            new_table = f"{table}_with_ownership"
            connection.exec_driver_sql(f"DROP TABLE IF EXISTS {new_table}")
            if table == "assignment":
                create_sql = f"""
                    CREATE TABLE {new_table} (
                        id INTEGER NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        subject VARCHAR(100) NOT NULL,
                        due_date DATE NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        user_id INTEGER NOT NULL REFERENCES user(id)
                    )
                """
            elif table == "note":
                create_sql = f"""
                    CREATE TABLE {new_table} (
                        id INTEGER NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        subject VARCHAR(100) NOT NULL,
                        content TEXT NOT NULL,
                        created_at DATETIME NOT NULL,
                        user_id INTEGER NOT NULL REFERENCES user(id)
                    )
                """
            else:
                create_sql = f"""
                    CREATE TABLE {new_table} (
                        id INTEGER NOT NULL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        due_date DATE NOT NULL,
                        completed BOOLEAN NOT NULL,
                        user_id INTEGER NOT NULL REFERENCES user(id)
                    )
                """
            connection.exec_driver_sql(create_sql)
            connection.exec_driver_sql(
                f"INSERT INTO {new_table} ({columns}) "
                f"SELECT {columns.replace(', user_id', '')}, :user_id FROM {table}",
                {"user_id": legacy_user.id},
            )
            connection.exec_driver_sql(f"DROP TABLE {table}")
            connection.exec_driver_sql(f"ALTER TABLE {new_table} RENAME TO {table}")
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        connection.close()


with app.app_context():
    db.create_all()
    migrate_ownership_columns()
    db.session.execute(
        db.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_user_email "
            "ON user (email)"
        )
    )
    db.session.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None or db.session.get(User, user_id) is None:
            session.clear()
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def current_user_id():
    user_id = session.get("user_id")
    if user_id is None:
        abort(401)
    return user_id


def assignment_to_dict(assignment):
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description or "",
        "subject": assignment.subject,
        "due_date": assignment.due_date.isoformat(),
        "status": assignment.status,
    }


def note_to_dict(note):
    return {
        "id": note.id,
        "title": note.title,
        "subject": note.subject,
        "content": note.content,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


def task_to_dict(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "due_date": task.due_date.isoformat(),
        "completed": bool(task.completed),
    }


def api_user_id():
    user_id = session.get("user_id")
    if user_id is None or db.session.get(User, user_id) is None:
        session.clear()
        return None
    return user_id


def assignment_json_payload():
    if not request.is_json:
        return None, jsonify(error="Request body must be valid JSON."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, jsonify(error="Request body must contain a JSON object."), 400
    return payload, None, None


def api_json_payload():
    if not request.is_json:
        return None, jsonify(error="Request body must be valid JSON."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, jsonify(error="Request body must contain a JSON object."), 400
    return payload, None, None


def validation_error_for_text(payload, field, required=True, max_length=None):
    value = payload.get(field)
    if value is None and not required:
        return None
    if not isinstance(value, str):
        return f"{field.replace('_', ' ').capitalize()} must be text."
    if required and not value.strip():
        return f"{field.replace('_', ' ').capitalize()} is required."
    if max_length and len(value.strip()) > max_length:
        return f"{field.replace('_', ' ').capitalize()} is too long."
    return None


def validate_note_payload(payload):
    allowed_fields = {"title", "subject", "content"}
    if set(payload) - allowed_fields:
        return "Request contains unsupported fields."
    for field in allowed_fields:
        error = validation_error_for_text(payload, field, max_length=MAX_LENGTHS[field])
        if error:
            return error
    return None


def validate_task_payload(payload):
    allowed_fields = {"title", "description", "due_date"}
    if set(payload) - allowed_fields:
        return "Request contains unsupported fields."
    for field in ("title", "description"):
        error = validation_error_for_text(
            payload, field, required=field == "title", max_length=MAX_LENGTHS[field]
        )
        if error:
            return error
    error = validation_error_for_text(payload, "due_date", max_length=10)
    if error:
        return error
    try:
        datetime.strptime(payload["due_date"], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return "Due date must use YYYY-MM-DD format."
    return None


def validate_assignment_payload(payload):
    allowed_fields = {"title", "description", "subject", "due_date", "status"}
    if set(payload) - allowed_fields:
        return "Request contains unsupported fields."
    for field in ("title", "description", "subject", "due_date", "status"):
        error = validation_error_for_text(
            payload,
            field,
            required=field not in {"description"},
            max_length=MAX_LENGTHS.get(field, 20),
        )
        if error:
            return error
    if payload["status"] not in ALLOWED_ASSIGNMENT_STATUSES:
        return "Status must be Pending or Completed."
    try:
        datetime.strptime(payload["due_date"], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return "Due date must use YYYY-MM-DD format."
    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/features")
def features():
    return render_template("features.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(email) > MAX_LENGTHS["email"] or len(password) > MAX_LENGTHS["password"]:
            return render_template("login.html", error="Invalid email or password.")
        user = db.session.scalar(db.select(User).where(User.email == email))

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["_csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid email or password.")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if (
            not name
            or not email
            or email.count("@") != 1
            or "." not in email.rsplit("@", 1)[-1]
            or not password
            or len(name) > MAX_LENGTHS["name"]
            or len(email) > MAX_LENGTHS["email"]
            or len(password) > MAX_LENGTHS["password"]
        ):
            return render_template(
                "signup.html",
                error="Name, email, and password are required.",
                form=request.form,
            )
        if password != confirm_password:
            return render_template(
                "signup.html",
                error="Passwords do not match.",
                form=request.form,
            )
        if db.session.scalar(db.select(User).where(User.email == email)):
            return render_template(
                "signup.html",
                error="An account with that email already exists.",
                form=request.form,
            )

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("signup.html", form={})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = current_user_id()
    user = db.session.get(User, user_id)
    return render_template(
        "dashboard.html",
        user=user,
        assignment_count=db.session.scalar(
            db.select(db.func.count(Assignment.id)).where(Assignment.user_id == user_id)
        ),
        note_count=db.session.scalar(
            db.select(db.func.count(Note.id)).where(Note.user_id == user_id)
        ),
        task_count=db.session.scalar(
            db.select(db.func.count(Task.id)).where(Task.user_id == user_id)
        ),
        completed_task_count=db.session.scalar(
            db.select(db.func.count(Task.id)).where(
                Task.user_id == user_id, Task.completed.is_(True)
            )
        ),
    )


@app.route("/api/dashboard/stats")
def dashboard_stats():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    stats = {
        "assignments": db.session.scalar(
            db.select(db.func.count(Assignment.id)).where(Assignment.user_id == user_id)
        ) or 0,
        "pending_assignments": db.session.scalar(
            db.select(db.func.count(Assignment.id)).where(
                Assignment.user_id == user_id, Assignment.status == "Pending"
            )
        ) or 0,
        "completed_assignments": db.session.scalar(
            db.select(db.func.count(Assignment.id)).where(
                Assignment.user_id == user_id, Assignment.status == "Completed"
            )
        ) or 0,
        "notes": db.session.scalar(
            db.select(db.func.count(Note.id)).where(Note.user_id == user_id)
        ) or 0,
        "tasks": db.session.scalar(
            db.select(db.func.count(Task.id)).where(Task.user_id == user_id)
        ) or 0,
        "completed_tasks": db.session.scalar(
            db.select(db.func.count(Task.id)).where(
                Task.user_id == user_id, Task.completed.is_(True)
            )
        ) or 0,
        "pending_tasks": db.session.scalar(
            db.select(db.func.count(Task.id)).where(
                Task.user_id == user_id, Task.completed.is_(False)
            )
        ) or 0,
    }
    return jsonify(stats)


@app.route("/api/dashboard/recent-assignments")
def dashboard_recent_assignments():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    assignments = db.session.scalars(
        db.select(Assignment)
        .where(Assignment.user_id == user_id)
        .order_by(Assignment.due_date.asc(), Assignment.id.asc())
        .limit(5)
    ).all()
    return jsonify(
        [
            {
                "id": assignment.id,
                "title": assignment.title,
                "subject": assignment.subject,
                "due_date": assignment.due_date.isoformat(),
                "status": assignment.status,
            }
            for assignment in assignments
        ]
    )


@app.route("/api/dashboard/recent-tasks")
def dashboard_recent_tasks():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    tasks = db.session.scalars(
        db.select(Task)
        .where(Task.user_id == user_id)
        .order_by(Task.due_date.asc(), Task.id.asc())
        .limit(5)
    ).all()
    return jsonify(
        [
            {
                "id": task.id,
                "title": task.title,
                "due_date": task.due_date.isoformat(),
                "completed": bool(task.completed),
            }
            for task in tasks
        ]
    )


@app.route("/assignments")
@login_required
def assignments():
    user_id = current_user_id()
    assignment_list = db.session.scalars(
        db.select(Assignment)
        .where(Assignment.user_id == user_id)
        .order_by(Assignment.due_date)
    ).all()
    return render_template("assignments.html", assignments=assignment_list)


@app.route("/api/assignments", methods=["GET"])
def api_assignments():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    assignment_list = db.session.scalars(
        db.select(Assignment)
        .where(Assignment.user_id == user_id)
        .order_by(Assignment.due_date)
    ).all()
    return jsonify(assignments=[assignment_to_dict(assignment) for assignment in assignment_list])


@app.route("/api/assignments", methods=["POST"])
def api_create_assignment():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    payload, error_response, status_code = assignment_json_payload()
    if error_response is not None:
        return error_response, status_code
    validation_error = validate_assignment_payload(payload)
    if validation_error:
        return jsonify(error=validation_error), 400

    assignment = Assignment(
        title=payload["title"].strip(),
        description=(payload.get("description") or "").strip(),
        subject=payload["subject"].strip(),
        due_date=datetime.strptime(payload["due_date"], "%Y-%m-%d").date(),
        status=payload["status"],
        user_id=user_id,
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify(assignment_to_dict(assignment)), 201


@app.route("/api/assignments/<int:id>", methods=["PUT"])
def api_update_assignment(id):
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    assignment = db.session.scalar(
        db.select(Assignment).where(Assignment.id == id, Assignment.user_id == user_id)
    )
    if assignment is None:
        return jsonify(error="Assignment not found."), 404

    payload, error_response, status_code = assignment_json_payload()
    if error_response is not None:
        return error_response, status_code
    validation_error = validate_assignment_payload(payload)
    if validation_error:
        return jsonify(error=validation_error), 400

    assignment.title = payload["title"].strip()
    assignment.description = str(payload.get("description", "")).strip()
    assignment.subject = payload["subject"].strip()
    assignment.due_date = datetime.strptime(payload["due_date"], "%Y-%m-%d").date()
    assignment.status = payload["status"]
    db.session.commit()
    return jsonify(assignment_to_dict(assignment))


@app.route("/api/assignments/<int:id>", methods=["DELETE"])
def api_delete_assignment(id):
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    assignment = db.session.scalar(
        db.select(Assignment).where(Assignment.id == id, Assignment.user_id == user_id)
    )
    if assignment is None:
        return jsonify(error="Assignment not found."), 404

    db.session.delete(assignment)
    db.session.commit()
    return jsonify(message="Assignment deleted successfully.")


@app.route("/api/notes", methods=["GET"])
def api_notes():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    note_list = db.session.scalars(
        db.select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc())
    ).all()
    return jsonify(notes=[note_to_dict(note) for note in note_list])


@app.route("/api/notes", methods=["POST"])
def api_create_note():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    payload, error_response, status_code = api_json_payload()
    if error_response is not None:
        return error_response, status_code

    validation_error = validate_note_payload(payload)
    if validation_error:
        return jsonify(error=validation_error), 400

    note = Note(
        title=payload["title"].strip(),
        subject=payload["subject"].strip(),
        content=payload["content"].strip(),
        user_id=user_id,
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(note_to_dict(note)), 201


@app.route("/api/notes/<int:id>", methods=["PUT"])
def api_update_note(id):
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    note = db.session.scalar(
        db.select(Note).where(Note.id == id, Note.user_id == user_id)
    )
    if note is None:
        return jsonify(error="Note not found."), 404

    payload, error_response, status_code = api_json_payload()
    if error_response is not None:
        return error_response, status_code

    validation_error = validate_note_payload(payload)
    if validation_error:
        return jsonify(error=validation_error), 400

    note.title = payload["title"].strip()
    note.subject = payload["subject"].strip()
    note.content = payload["content"].strip()
    db.session.commit()
    return jsonify(note_to_dict(note))


@app.route("/api/notes/<int:id>", methods=["DELETE"])
def api_delete_note(id):
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    note = db.session.scalar(
        db.select(Note).where(Note.id == id, Note.user_id == user_id)
    )
    if note is None:
        return jsonify(error="Note not found."), 404

    db.session.delete(note)
    db.session.commit()
    return jsonify(message="Note deleted successfully.")


@app.route("/api/tasks", methods=["GET"])
def api_tasks():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    task_list = db.session.scalars(
        db.select(Task).where(Task.user_id == user_id).order_by(Task.due_date)
    ).all()
    return jsonify(tasks=[task_to_dict(task) for task in task_list])


@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    payload, error_response, status_code = api_json_payload()
    if error_response is not None:
        return error_response, status_code

    validation_error = validate_task_payload(payload)
    if validation_error:
        return jsonify(error=validation_error), 400

    task = Task(
        title=payload["title"].strip(),
        description=(payload.get("description") or "").strip(),
        due_date=datetime.strptime(payload["due_date"], "%Y-%m-%d").date(),
        completed=False,
        user_id=user_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task_to_dict(task)), 201


@app.route("/api/tasks/<int:id>", methods=["PUT"])
def api_update_task(id):
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    task = db.session.scalar(
        db.select(Task).where(Task.id == id, Task.user_id == user_id)
    )
    if task is None:
        return jsonify(error="Task not found."), 404

    payload, error_response, status_code = api_json_payload()
    if error_response is not None:
        return error_response, status_code

    validation_error = validate_task_payload(payload)
    if validation_error:
        return jsonify(error=validation_error), 400

    task.title = payload["title"].strip()
    task.description = (payload.get("description") or "").strip()
    task.due_date = datetime.strptime(payload["due_date"], "%Y-%m-%d").date()
    db.session.commit()
    return jsonify(task_to_dict(task))


@app.route("/api/tasks/<int:id>", methods=["DELETE"])
def api_delete_task(id):
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    task = db.session.scalar(
        db.select(Task).where(Task.id == id, Task.user_id == user_id)
    )
    if task is None:
        return jsonify(error="Task not found."), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify(message="Task deleted successfully.")


@app.route("/api/tasks/<int:id>/toggle", methods=["POST"])
def api_toggle_task(id):
    user_id = api_user_id()
    if user_id is None:
        return jsonify(error="Authentication is required."), 401

    task = db.session.scalar(
        db.select(Task).where(Task.id == id, Task.user_id == user_id)
    )
    if task is None:
        return jsonify(error="Task not found."), 404

    task.completed = not task.completed
    db.session.commit()
    return jsonify(task_to_dict(task))


@app.route("/assignments/add", methods=["GET", "POST"])
@login_required
def add_assignment():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        subject = request.form.get("subject", "").strip()
        due_date_text = request.form.get("due_date", "")
        status = request.form.get("status", "")

        if (
            not title
            or not subject
            or not due_date_text
            or len(title) > MAX_LENGTHS["title"]
            or len(description) > MAX_LENGTHS["description"]
            or len(subject) > MAX_LENGTHS["subject"]
        ):
            return render_template(
                "add_assignment.html",
                error="Title, subject, and due date are required.",
                form=request.form,
            )
        if status not in {"Pending", "Completed"}:
            return render_template(
                "add_assignment.html",
                error="Status must be Pending or Completed.",
                form=request.form,
            )
        try:
            due_date = datetime.strptime(due_date_text, "%Y-%m-%d").date()
        except ValueError:
            return render_template(
                "add_assignment.html",
                error="Please enter a valid due date.",
                form=request.form,
            )

        assignment = Assignment(
            title=title,
            description=description,
            subject=subject,
            due_date=due_date,
            status=status,
            user_id=current_user_id(),
        )
        db.session.add(assignment)
        db.session.commit()
        return redirect(url_for("assignments"))

    return render_template("add_assignment.html", form={})


@app.route("/assignments/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_assignment(id):
    assignment = db.one_or_404(
        db.select(Assignment).where(
            Assignment.id == id, Assignment.user_id == current_user_id()
        )
    )

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        subject = request.form.get("subject", "").strip()
        due_date_text = request.form.get("due_date", "")
        status = request.form.get("status", "")

        if (
            not title
            or not subject
            or not due_date_text
            or len(title) > MAX_LENGTHS["title"]
            or len(description) > MAX_LENGTHS["description"]
            or len(subject) > MAX_LENGTHS["subject"]
        ):
            return render_template(
                "edit_assignment.html",
                assignment=assignment,
                error="Title, subject, and due date are required.",
                form=request.form,
            )
        if status not in {"Pending", "Completed"}:
            return render_template(
                "edit_assignment.html",
                assignment=assignment,
                error="Status must be Pending or Completed.",
                form=request.form,
            )
        try:
            due_date = datetime.strptime(due_date_text, "%Y-%m-%d").date()
        except ValueError:
            return render_template(
                "edit_assignment.html",
                assignment=assignment,
                error="Please enter a valid due date.",
                form=request.form,
            )

        assignment.title = title
        assignment.description = description
        assignment.subject = subject
        assignment.due_date = due_date
        assignment.status = status
        db.session.commit()
        return redirect(url_for("assignments"))

    return render_template("edit_assignment.html", assignment=assignment, form={})


@app.route("/assignments/delete/<int:id>", methods=["POST"])
@login_required
def delete_assignment(id):
    assignment = db.one_or_404(
        db.select(Assignment).where(
            Assignment.id == id, Assignment.user_id == current_user_id()
        )
    )
    db.session.delete(assignment)
    db.session.commit()
    return redirect(url_for("assignments"))


@app.route("/notes")
@login_required
def notes():
    user_id = current_user_id()
    note_list = db.session.scalars(
        db.select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc())
    ).all()
    return render_template("notes.html", notes=note_list)


@app.route("/notes/add", methods=["GET", "POST"])
@login_required
def add_note():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        content = request.form.get("content", "").strip()

        if (
            not title
            or not subject
            or not content
            or len(title) > MAX_LENGTHS["title"]
            or len(subject) > MAX_LENGTHS["subject"]
            or len(content) > MAX_LENGTHS["content"]
        ):
            return render_template(
                "add_note.html",
                error="Title, subject, and content are required.",
                form=request.form,
            )

        note = Note(
            title=title,
            subject=subject,
            content=content,
            user_id=current_user_id(),
        )
        db.session.add(note)
        db.session.commit()
        return redirect(url_for("notes"))

    return render_template("add_note.html", form={})


@app.route("/notes/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_note(id):
    note = db.one_or_404(
        db.select(Note).where(Note.id == id, Note.user_id == current_user_id())
    )

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        content = request.form.get("content", "").strip()

        if (
            not title
            or not subject
            or not content
            or len(title) > MAX_LENGTHS["title"]
            or len(subject) > MAX_LENGTHS["subject"]
            or len(content) > MAX_LENGTHS["content"]
        ):
            return render_template(
                "edit_note.html",
                note=note,
                error="Title, subject, and content are required.",
                form=request.form,
            )

        note.title = title
        note.subject = subject
        note.content = content
        db.session.commit()
        return redirect(url_for("notes"))

    return render_template("edit_note.html", note=note, form={})


@app.route("/notes/delete/<int:id>", methods=["POST"])
@login_required
def delete_note(id):
    note = db.one_or_404(
        db.select(Note).where(Note.id == id, Note.user_id == current_user_id())
    )
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for("notes"))


@app.route("/tasks")
@login_required
def tasks():
    user_id = current_user_id()
    task_list = db.session.scalars(
        db.select(Task).where(Task.user_id == user_id).order_by(Task.due_date)
    ).all()
    return render_template("tasks.html", tasks=task_list)


@app.route("/tasks/add", methods=["GET", "POST"])
@login_required
def add_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date_text = request.form.get("due_date", "")

        if (
            not title
            or not due_date_text
            or len(title) > MAX_LENGTHS["title"]
            or len(description) > MAX_LENGTHS["description"]
        ):
            return render_template(
                "add_task.html",
                error="Title and due date are required.",
                form=request.form,
            )

        try:
            due_date = datetime.strptime(due_date_text, "%Y-%m-%d").date()
        except ValueError:
            return render_template(
                "add_task.html",
                error="Please enter a valid due date.",
                form=request.form,
            )

        task = Task(
            title=title,
            description=description,
            due_date=due_date,
            user_id=current_user_id(),
        )
        db.session.add(task)
        db.session.commit()
        return redirect(url_for("tasks"))

    return render_template("add_task.html", form={})


@app.route("/tasks/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_task(id):
    task = db.one_or_404(
        db.select(Task).where(Task.id == id, Task.user_id == current_user_id())
    )

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date_text = request.form.get("due_date", "")

        if (
            not title
            or not due_date_text
            or len(title) > MAX_LENGTHS["title"]
            or len(description) > MAX_LENGTHS["description"]
        ):
            return render_template(
                "edit_task.html",
                task=task,
                error="Title and due date are required.",
                form=request.form,
            )

        try:
            due_date = datetime.strptime(due_date_text, "%Y-%m-%d").date()
        except ValueError:
            return render_template(
                "edit_task.html",
                task=task,
                error="Please enter a valid due date.",
                form=request.form,
            )

        task.title = title
        task.description = description
        task.due_date = due_date
        db.session.commit()
        return redirect(url_for("tasks"))

    return render_template("edit_task.html", task=task, form={})


@app.route("/tasks/delete/<int:id>", methods=["POST"])
@login_required
def delete_task(id):
    task = db.one_or_404(
        db.select(Task).where(Task.id == id, Task.user_id == current_user_id())
    )
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("tasks"))


@app.route("/tasks/toggle/<int:id>", methods=["POST"])
@login_required
def toggle_task(id):
    task = db.one_or_404(
        db.select(Task).where(Task.id == id, Task.user_id == current_user_id())
    )
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for("tasks"))


def is_api_request():
    return request.path.startswith("/api/")


def error_response(status_code, message):
    if is_api_request():
        return jsonify(error=message), status_code
    return render_template(
        "error.html", status_code=status_code, message=message
    ), status_code


@app.errorhandler(400)
def handle_bad_request(error):
    return error_response(400, "The request could not be understood.")


@app.errorhandler(401)
def handle_unauthorized(error):
    return error_response(401, "Authentication is required.")


@app.errorhandler(403)
def handle_forbidden(error):
    return error_response(403, "You are not allowed to perform that action.")


@app.errorhandler(404)
def handle_not_found(error):
    return error_response(404, "The requested page or record was not found.")


@app.errorhandler(405)
def handle_method_not_allowed(error):
    return error_response(405, "This method is not allowed for the requested resource.")


@app.errorhandler(500)
def handle_internal_error(error):
    db.session.rollback()
    return error_response(500, "An unexpected error occurred. Please try again.")


if __name__ == "__main__":
    app.run(debug=not is_production)
