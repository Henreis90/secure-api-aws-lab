import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps

import bcrypt
import jwt
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, g, make_response

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 30

# Armazenamento didático em memória para sessões
# Depois podemos evoluir para Redis ou banco
SESSIONS = {}


def get_db_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )


def ensure_notes_table_exists():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def ensure_users_table_exists():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def seed_default_users():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        default_users = [
            {"username": "user1", "password": "Password123!", "role": "user"},
            {"username": "admin", "password": "Admin123!", "role": "admin"},
        ]

        for user in default_users:
            cur.execute(
                "SELECT id FROM users WHERE username = %s;",
                (user["username"],)
            )
            existing = cur.fetchone()
            if existing:
                continue

            password_hash = bcrypt.hashpw(
                user["password"].encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            cur.execute(
                """
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s);
                """,
                (user["username"], password_hash, user["role"])
            )

        conn.commit()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def json_error(message, status_code, details=None):
    payload = {
        "error": message,
        "status": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


def get_user_by_username(username):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, username, password_hash, role, created_at
            FROM users
            WHERE username = %s;
            """,
            (username,)
        )
        return cur.fetchone()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def create_jwt(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXP_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token):
#    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
#UNSAFE:
    return jwt.decode(token, options={"verify_signature": False})


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def get_current_user_from_session():
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    session_data = SESSIONS.get(session_id)
    if not session_data:
        return None

    expires_at = session_data["expires_at"]
    if datetime.now(timezone.utc) > expires_at:
        del SESSIONS[session_id]
        return None

    return session_data["user"]


def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = get_bearer_token()
        if not token:
            return json_error("Missing Bearer token", 401)

        try:
            payload = decode_jwt(token)
            g.current_user = {
                "id": payload["sub"],
                "username": payload["username"],
                "role": payload["role"],
                "auth_type": "jwt"
            }
        except jwt.ExpiredSignatureError:
            return json_error("Token expired", 401)
        except jwt.InvalidTokenError:
            return json_error("Invalid token", 401)

        return fn(*args, **kwargs)
    return wrapper


def session_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user_from_session()
        if not user:
            return json_error("Missing or invalid session", 401)

        g.current_user = {
            **user,
            "auth_type": "session"
        }
        return fn(*args, **kwargs)
    return wrapper


def role_required(required_role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            current_user = getattr(g, "current_user", None)
            if not current_user:
                return json_error("Authentication required", 401)

            if current_user.get("role") != required_role:
                return json_error("Forbidden", 403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.before_request
def log_request():
    logger.info(
        "Request received: method=%s path=%s remote_addr=%s",
        request.method,
        request.path,
        request.remote_addr
    )


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "Secure API is running",
        "version": "3.0",
        "endpoints": [
            "GET /",
            "GET /health",
            "GET /db-version",
            "GET /request-info",
            "POST /login-jwt",
            "POST /login-session",
            "POST /logout-session",
            "GET /profile-jwt",
            "GET /profile-session",
            "GET /admin-jwt",
            "GET /admin-session",
            "GET /notes",
            "GET /notes/<id>",
            "POST /notes",
            "PUT /notes/<id>",
            "PATCH /notes/<id>",
            "DELETE /notes/<id>"
        ]
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/db-version", methods=["GET"])
def db_version():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]

        return jsonify({"postgres_version": version}), 200

    except Exception as exc:
        logger.exception("Database connection failed")
        return json_error("Database connection failed", 500, str(exc))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/request-info", methods=["GET", "POST"])
def request_info():
    return jsonify({
        "method": request.method,
        "path": request.path,
        "query_params": request.args.to_dict(),
        "headers": {k: v for k, v in request.headers.items()},
        "json_body": request.get_json(silent=True)
    }), 200


@app.route("/login-jwt", methods=["POST"])
def login_jwt():
    if not request.is_json:
        return json_error("Content-Type must be application/json", 415)

    data = request.get_json(silent=True)
    if data is None:
        return json_error("Invalid JSON body", 400)

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return json_error("Username and password are required", 400)

    user = get_user_by_username(username)
    if not user:
        return json_error("Invalid credentials", 401)

    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return json_error("Invalid credentials", 401)

    token = create_jwt(user)

    logger.info("JWT login successful for username=%s", username)

    return jsonify({
        "message": "Login successful",
        "access_token": token,
        "token_type": "Bearer"
    }), 200


@app.route("/login-session", methods=["POST"])
def login_session():
    if not request.is_json:
        return json_error("Content-Type must be application/json", 415)

    data = request.get_json(silent=True)
    if data is None:
        return json_error("Invalid JSON body", 400)

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return json_error("Username and password are required", 400)

    user = get_user_by_username(username)
    if not user:
        return json_error("Invalid credentials", 401)

    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return json_error("Invalid credentials", 401)

    session_id = secrets.token_urlsafe(32)
# UNSAFE:  
# session_id = request.cookies.get("session_id") or secrets.token_urlsafe(32)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    SESSIONS[session_id] = {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"]
        },
        "expires_at": expires_at
    }

    logger.info("Session login successful for username=%s", username)

    response = make_response(jsonify({
        "message": "Session login successful"
    }), 200)

    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=1800
    )

    return response


@app.route("/logout-session", methods=["POST"])
def logout_session():
    session_id = request.cookies.get("session_id")
    if session_id and session_id in SESSIONS:
        del SESSIONS[session_id]

    response = make_response(jsonify({
        "message": "Logged out successfully"
    }), 200)
    response.delete_cookie("session_id")
    return response


@app.route("/profile-jwt", methods=["GET"])
@jwt_required
def profile_jwt():
    return jsonify({
        "message": "Authenticated with JWT",
        "user": g.current_user
    }), 200


@app.route("/profile-session", methods=["GET"])
@session_required
def profile_session():
    return jsonify({
        "message": "Authenticated with session cookie",
        "user": g.current_user
    }), 200


@app.route("/admin-jwt", methods=["GET"])
@jwt_required
@role_required("admin")
def admin_jwt():
    return jsonify({
        "message": "Admin area via JWT",
        "user": g.current_user
    }), 200


@app.route("/admin-session", methods=["GET"])
@session_required
@role_required("admin")
def admin_session():
    return jsonify({
        "message": "Admin area via session",
        "user": g.current_user
    }), 200


@app.route("/notes", methods=["GET"])
def list_notes():
    conn = None
    cur = None

    try:
        ensure_notes_table_exists()

        search = request.args.get("search")

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if search:
            cur.execute(
                """
                SELECT id, title, content, created_at, updated_at
                FROM notes
                WHERE title ILIKE %s OR content ILIKE %s
                ORDER BY id ASC;
                """,
                (f"%{search}%", f"%{search}%")
            )
        else:
            cur.execute(
                """
                SELECT id, title, content, created_at, updated_at
                FROM notes
                ORDER BY id ASC;
                """
            )

        notes = cur.fetchall()

        return jsonify({
            "count": len(notes),
            "items": notes
        }), 200

    except Exception as exc:
        logger.exception("Failed to list notes")
        return json_error("Failed to list notes", 500, str(exc))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/notes/<int:note_id>", methods=["GET"])
def get_note(note_id):
    conn = None
    cur = None

    try:
        ensure_notes_table_exists()

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, title, content, created_at, updated_at
            FROM notes
            WHERE id = %s;
            """,
            (note_id,)
        )
        note = cur.fetchone()

        if not note:
            return json_error("Note not found", 404)

        return jsonify(note), 200

    except Exception as exc:
        logger.exception("Failed to get note")
        return json_error("Failed to get note", 500, str(exc))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/notes", methods=["POST"])
def create_note():
    conn = None
    cur = None

    try:
        ensure_notes_table_exists()

        if not request.is_json:
            return json_error("Content-Type must be application/json", 415)

        data = request.get_json(silent=True)
        if data is None:
            return json_error("Invalid JSON body", 400)

        title = data.get("title")
        content = data.get("content")

        validation_errors = []

        if not title or not isinstance(title, str):
            validation_errors.append("Field 'title' is required and must be a string")

        if not content or not isinstance(content, str):
            validation_errors.append("Field 'content' is required and must be a string")

        if validation_errors:
            return json_error("Validation failed", 422, validation_errors)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO notes (title, content)
            VALUES (%s, %s)
            RETURNING id, title, content, created_at, updated_at;
            """,
            (title, content)
        )
        created_note = cur.fetchone()
        conn.commit()

        return jsonify({
            "message": "Note created successfully",
            "item": created_note
        }), 201

    except Exception as exc:
        logger.exception("Failed to create note")
        return json_error("Failed to create note", 500, str(exc))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/notes/<int:note_id>", methods=["PUT"])
def replace_note(note_id):
    conn = None
    cur = None

    try:
        ensure_notes_table_exists()

        if not request.is_json:
            return json_error("Content-Type must be application/json", 415)

        data = request.get_json(silent=True)
        if data is None:
            return json_error("Invalid JSON body", 400)

        title = data.get("title")
        content = data.get("content")

        validation_errors = []

        if not title or not isinstance(title, str):
            validation_errors.append("Field 'title' is required and must be a string")

        if not content or not isinstance(content, str):
            validation_errors.append("Field 'content' is required and must be a string")

        if validation_errors:
            return json_error("Validation failed", 422, validation_errors)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT id FROM notes WHERE id = %s;", (note_id,))
        existing = cur.fetchone()
        if not existing:
            return json_error("Note not found", 404)

        cur.execute(
            """
            UPDATE notes
            SET title = %s,
                content = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, title, content, created_at, updated_at;
            """,
            (title, content, note_id)
        )
        updated_note = cur.fetchone()
        conn.commit()

        return jsonify({
            "message": "Note replaced successfully",
            "item": updated_note
        }), 200

    except Exception as exc:
        logger.exception("Failed to replace note")
        return json_error("Failed to replace note", 500, str(exc))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/notes/<int:note_id>", methods=["PATCH"])
def update_note_partial(note_id):
    conn = None
    cur = None

    try:
        ensure_notes_table_exists()

        if not request.is_json:
            return json_error("Content-Type must be application/json", 415)

        data = request.get_json(silent=True)
        if data is None:
            return json_error("Invalid JSON body", 400)

        allowed_fields = {"title", "content"}
        received_fields = set(data.keys())

        if not received_fields:
            return json_error("At least one field must be provided", 400)

        invalid_fields = list(received_fields - allowed_fields)
        if invalid_fields:
            return json_error("Invalid fields in request", 422, invalid_fields)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT id, title, content, created_at, updated_at
            FROM notes
            WHERE id = %s;
            """,
            (note_id,)
        )
        existing = cur.fetchone()

        if not existing:
            return json_error("Note not found", 404)

        new_title = data.get("title", existing["title"])
        new_content = data.get("content", existing["content"])

        if not isinstance(new_title, str) or not new_title.strip():
            return json_error("Field 'title' must be a non-empty string", 422)

        if not isinstance(new_content, str) or not new_content.strip():
            return json_error("Field 'content' must be a non-empty string", 422)

        cur.execute(
            """
            UPDATE notes
            SET title = %s,
                content = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, title, content, created_at, updated_at;
            """,
            (new_title, new_content, note_id)
        )
        updated_note = cur.fetchone()
        conn.commit()

        return jsonify({
            "message": "Note updated successfully",
            "item": updated_note
        }), 200

    except Exception as exc:
        logger.exception("Failed to partially update note")
        return json_error("Failed to partially update note", 500, str(exc))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    conn = None
    cur = None

    try:
        ensure_notes_table_exists()

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT id, title, content, created_at, updated_at
            FROM notes
            WHERE id = %s;
            """,
            (note_id,)
        )
        existing = cur.fetchone()

        if not existing:
            return json_error("Note not found", 404)

        cur.execute("DELETE FROM notes WHERE id = %s;", (note_id,))
        conn.commit()

        return "", 204

    except Exception as exc:
        logger.exception("Failed to delete note")
        return json_error("Failed to delete note", 500, str(exc))

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.errorhandler(404)
def not_found(_error):
    return json_error("Route not found", 404)


@app.errorhandler(405)
def method_not_allowed(_error):
    return json_error("Method not allowed for this route", 405)


@app.errorhandler(500)
def internal_error(_error):
    return json_error("Internal server error", 500)

ensure_notes_table_exists()
ensure_users_table_exists()
seed_default_users()

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=8080)