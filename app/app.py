import logging
import os
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger(__name__)


def get_db_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )


def ensure_table_exists():
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


def json_error(message, status_code, details=None):
    payload = {
        "error": message,
        "status": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


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
        "version": "2.0",
        "endpoints": [
            "GET /",
            "GET /health",
            "GET /db-version",
            "GET /request-info",
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


@app.route("/notes", methods=["GET"])
def list_notes():
    conn = None
    cur = None

    try:
        ensure_table_exists()

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
        ensure_table_exists()

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
        ensure_table_exists()

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
        ensure_table_exists()

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
        ensure_table_exists()

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
        ensure_table_exists()

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


if __name__ == "__main__":
    ensure_table_exists()
    app.run(host="0.0.0.0", port=8080)