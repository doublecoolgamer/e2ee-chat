from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import os
from decrypter import encrypt_bytes, decrypt_bytes

app = Flask(__name__, static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")  # real-time support

OWNER_TOKEN = os.environ.get("OWNER_TOKEN", "B25X25kfqAbC123")
DB_PATH = "messages.db"

# ----------------- DATABASE SETUP -----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        ciphertext TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------- DASHBOARD -----------------
@app.route('/')
def dashboard():
    token = request.args.get('token', '')
    if token != OWNER_TOKEN:
        return "Access denied", 403
    return send_from_directory(app.static_folder, 'dashboard.html')

# ----------------- SOCKET EVENTS -----------------
@socketio.on('send_message')
def handle_send(data):
    sender = data.get('sender')
    receiver = data.get('receiver')
    message = data.get('message')

    if not sender or not receiver or not message:
        emit('error', {'msg': 'Missing fields'})
        return

    # Encrypt message
    encrypted = encrypt_bytes(message.encode()).hex()

    # Save to DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender, receiver, ciphertext) VALUES (?, ?, ?)",
              (sender, receiver, encrypted))
    conn.commit()
    conn.close()

    # Emit message to receiver room
    emit('receive_message', {'sender': sender, 'message': message}, room=receiver)

# Join room (username)
@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    if username:
        join_room(username)

# Fetch messages
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
            "message": decrypt_bytes(bytes.fromhex(ciphertext_hex)).decode(),
            "timestamp": timestamp
        })

    return jsonify({"messages": decrypted_messages})

# ----------------- RUN SERVER -----------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
