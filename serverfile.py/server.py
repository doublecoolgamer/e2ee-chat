# server.py
import os
import sqlite3
import base64
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort

# Configuration (use environment variables in production)
UPLOAD_TOKEN = os.environ.get("UPLOAD_TOKEN", "upload-secret-token")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "B25X25kfq")
SERVER = "http://127.0.0.1:5000"
DB_PATH = os.environ.get("DB_PATH", "messages.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        sender TEXT,
        ciphertext TEXT,         -- base64 of AES-GCM ciphertext including tag
        iv TEXT,                 -- base64 IV used for AES-GCM
        encrypted_key TEXT,      -- base64 RSA-OAEP encrypted AES key
        timestamp TEXT
    )
    """)
    conn.commit()
    conn.close()

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "client.html")

@app.route("/api/messages", methods=["POST"])
def post_message():
    """
    Expected JSON:
    {
      "upload_token": "...",            # optional but recommended
      "chat_id": "chat-123",
      "sender": "alice",
      "ciphertext": "<base64>",
      "iv": "<base64>",
      "encrypted_key": "<base64>"
    }
    The server stores only the ciphertext pieces. No private keys here.
    """
    j = request.get_json(force=True)
    token = j.get("upload_token")
    if token != UPLOAD_TOKEN:
        return jsonify({"error": "invalid upload token"}), 401

    required = ("chat_id", "sender", "ciphertext", "iv", "encrypted_key")
    if not all(k in j for k in required):
        return jsonify({"error": "missing fields"}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (chat_id, sender, ciphertext, iv, encrypted_key, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (j["chat_id"], j["sender"], j["ciphertext"], j["iv"], j["encrypted_key"], datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 201

@app.route("/api/messages", methods=["GET"])
def get_messages():
    """
    Admin endpoint to fetch all messages (ciphertext only).
    Provide admin token as query param ?admin_token=...
    In production: use proper auth (OAuth/JWT) + HTTPS.
    """
    token = request.args.get("admin_token")
    if token != ADMIN_TOKEN:
        return jsonify({"error": "unauthorized"}), 401

    chat_id = request.args.get("chat_id")  # optional filter

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if chat_id:
        cur.execute("SELECT id, chat_id, sender, ciphertext, iv, encrypted_key, timestamp FROM messages WHERE chat_id=? ORDER BY id ASC", (chat_id,))
    else:
        cur.execute("SELECT id, chat_id, sender, ciphertext, iv, encrypted_key, timestamp FROM messages ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    msgs = []
    for r in rows:
        msgs.append({
            "id": r[0],
            "chat_id": r[1],
            "sender": r[2],
            "ciphertext": r[3],
            "iv": r[4],
            "encrypted_key": r[5],
            "timestamp": r[6],
        })
    return jsonify({"messages": msgs})

@app.route("/api/messages/<int:msg_id>", methods=["DELETE"])
def delete_message(msg_id):
    token = request.args.get("admin_token")
    if token != ADMIN_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    init_db()
    # Note: In production, run behind gunicorn/uvicorn and use TLS (HTTPS).
    app.run(host="0.0.0.0", port=5000, debug=True)
