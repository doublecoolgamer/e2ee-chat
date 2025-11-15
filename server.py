# server.py
from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import os
from cryptography.fernet import Fernet

# ---------------- CONFIG ----------------
app = Flask(__name__, static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")

OWNER_TOKEN = os.getenv("OWNER_TOKEN", "B25X25kfqAbC123")
FERNET_KEY = os.getenv("FERNET_KEY")
DB_PATH = "messages.db"

if not FERNET_KEY:
    raise ValueError("FERNET_KEY environment variable not set")
cipher = Fernet(FERNET_KEY.encode())

# ------------- DATABASE INIT ------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
            ciphertext TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ------------- DASHBOARD ----------------
@app.route('/')
def dashboard():
    token = request.args.get('token', '')
    if token != OWNER_TOKEN:
        return "Access denied", 403
    return send_from_directory(app.static_folder, 'dashboard.html')

# ------------- SEND MESSAGE -------------
@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.get_json()
    sender = data.get('sender')
    receiver = data.get('receiver')
    message = data.get('message')

    if not sender or not receiver or not message:
        return jsonify({"error": "Missing fields"}), 400

    encrypted = cipher.encrypt(message.encode()).hex()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender, receiver, ciphertext, timestamp) VALUES (?, ?, ?, datetime('now'))",
              (sender, receiver, encrypted))
    conn.commit()
    conn.close()

    # Real-time emit
    socketio.emit('new_message', {"sender": sender, "message": message}, room=receiver)
    return jsonify({"status": "Message sent and stored"}), 201

# --------- FETCH MESSAGES -------------
@app.route('/api/messages/<username>', methods=['GET'])
def fetch_messages(username):
    token = request.args.get('token', '')
    if token != OWNER_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT sender, ciphertext, timestamp FROM messages WHERE receiver=?", (username,))
    rows = c.fetchall()
    conn.close()

    decrypted_messages = []
    for sender, ciphertext_hex, timestamp in rows:
        decrypted_messages.append({
            "sender": sender,
            "message": cipher.decrypt(bytes.fromhex(ciphertext_hex)).decode(),
            "timestamp": timestamp
        })

    return jsonify({"messages": decrypted_messages})
# --------- SOCKETIO ROOMS -------------
@socketio.on('join')
def on_join(data):
    username = data['username']
    join_room(username)
    print(f"{username} joined their room")

# --------- RUN SERVER ------------------
from flask_socketio import SocketIO

socketio = SocketIO(app, cors_allowed_origins="*")
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

