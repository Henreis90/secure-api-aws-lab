import logging
import os

import psycopg2
from flask import Flask, jsonify

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


@app.route("/health", methods=["GET"])
def health():
    logger.info("Health check called")
    return jsonify({"status": "ok"}), 200


@app.route("/db-version", methods=["GET"])
def db_version():
    logger.info("DB version endpoint called")

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]

        logger.info("Database connection successful")
        return jsonify({"postgres_version": version}), 200

    except Exception as exc:
        logger.exception("Database connection failed")
        return jsonify({"error": str(exc)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/", methods=["GET"])
def root():
    logger.info("Root endpoint called")
    return jsonify({"message": "Secure API is running"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
