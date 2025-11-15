# server_e2ee.py
import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_socketio import SocketIO, emit, join_room, leave_room

APP_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(APP_DIR, "messages.db")
STATIC_DIR = os.path.join(APP_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET", "dev-secret")
socketio = SocketIO(app, cors_allowed_origins="*")  # cors_allowed_origins restrict in prod

# In-memory map username -> socket session id (works for single-process dev)
connected = {}  # username -> sid

# Initialize DB if needed
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        pubkey TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        ephemeral TEXT,
        iv TEXT,
        ciphertext TEXT,
        timestamp TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# -------------------------
# Key directory endpoints
# -------------------------
@app.route("/api/keys", methods=["POST"])
def register_key():
    """
    Request json: { "username": "alice", "pubkey": "<base64 raw public key>" }
    """
    data = request.get_json()
    username = data.get("username")
    pubkey = data.get("pubkey")
    if not username or not pubkey:
        return jsonify({"error":"missing fields"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (username, pubkey) VALUES (?, ?)", (username, pubkey))
    conn.commit()
    conn.close()
    return jsonify({"status":"ok"}), 201

@app.route("/api/keys/<username>", methods=["GET"])
def get_key(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT pubkey FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({"error":"not found"}), 404
    return jsonify({"username": username, "pubkey": row[0]})

# -------------------------
# Message endpoints
# -------------------------
@app.route("/api/send", methods=["POST"])
def api_send():
    """
    Sender posts:
    {
      "sender":"alice",
      "receiver":"bob",
      "ephemeral": "<base64 raw ephemeral pub>",
      "iv": "<base64 iv>",
      "ciphertext": "<base64 ciphertext>"
    }
    """
    data = request.get_json()
    required = ("sender","receiver","ephemeral","iv","ciphertext")
    if not data or not all(k in data for k in required):
        return jsonify({"error":"missing fields"}), 400

    sender = data["sender"]
    receiver = data["receiver"]
    eph = data["ephemeral"]
    iv = data["iv"]
    ct = data["ciphertext"]
    timestamp = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender, receiver, ephemeral, iv, ciphertext, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (sender, receiver, eph, iv, ct, timestamp))
    msg_id = c.lastrowid
    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    return send_from_directory('static', 'dashboard.html')


    # If receiver is connected via websocket, push message
    sid = connected.get(receiver)
    payload = {"id": msg_id, "sender": sender, "ephemeral": eph, "iv": iv, "ciphertext": ct, "timestamp": timestamp}
    if sid:
        socketio.emit("message", payload, to=sid)

    return jsonify({"status":"stored","id":msg_id}), 201

@app.route("/api/messages/<username>", methods=["GET"])
def api_get_messages(username):
    # Returns stored messages for username (ciphertexts only)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, sender, ephemeral, iv, ciphertext, timestamp FROM messages WHERE receiver=? ORDER BY id ASC", (username,))
    rows = c.fetchall()
    conn.close()
    messages = []
    for r in rows:
        messages.append({
            "id": r[0],
            "sender": r[1],
            "ephemeral": r[2],
            "iv": r[3],
            "ciphertext": r[4],
            "timestamp": r[5]
        })
    return jsonify({"messages": messages})

# -------------------------
# Static UI
# -------------------------
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "send.html")

# -------------------------
# WebSocket handlers
# -------------------------
@socketio.on("connect")
def on_connect():
    # no-op; client must send 'identify' with username
    pass

@socketio.on("identify")
def on_identify(data):
    """
    data: { "username": "bob" }
    """
    username = data.get("username")
    if not username:
        return
    connected[username] = request.sid
    join_room(request.sid)
    print(f"{username} connected, sid={request.sid}")

@socketio.on("disconnect")
def on_disconnect():
    # remove any mapping with this sid
    sid = request.sid
    to_remove = [u for u, s in connected.items() if s == sid]
    for u in to_remove:
        connected.pop(u, None)
        print(f"{u} disconnected")

if __name__ == "__main__":
    # Use eventlet or gevent for production-like socket support
    # from terminal: export FLASK_SECRET="..." ; python server_e2ee.py
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
