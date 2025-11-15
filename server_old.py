from functools import wraps
from flask import request, abort

# Set your secret admin token here
ADMIN_TOKEN = "B25X25kfq"  # you can change this to a strong random string

def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get("admin_token")
        if token != ADMIN_TOKEN:
            abort(403, description="You don't have authorization to open this page")
        return f(*args, **kwargs)
    return decorated


from flask import Flask, request, jsonify
from flask import Flask, request, send_file, jsonify, render_template_string
app = Flask(__name__)

from flask import Flask, request, jsonify, send_file, render_template_string
import sqlite3
import datetime
from decrypter import decrypt_bytes

app = Flask(__name__)


# -------------------
# DATABASE FUNCTIONS
# -------------------
def db():
    return sqlite3.connect("messages.db")


def store_message(sender, receiver, ciphertext):
    conn = db()
    c = conn.cursor()

    c.execute("""
        INSERT INTO messages (sender, receiver, ciphertext, timestamp) 
        VALUES (?, ?, ?, ?)
    """, (
        sender,
        receiver,
        ciphertext,
        datetime.datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()


def fetch_all_messages():
    conn = db()
    c = conn.cursor()

    c.execute("SELECT * FROM messages ORDER BY id DESC")
    rows = c.fetchall()

    conn.close()
    return rows


# -------------------
#       ROUTES
# -------------------

# Homepage Web UI
@app.route("/")
def home():
    return """
    <h1>Owner Decrypt Web Interface</h1>

    <h2>Upload Encrypted Message</h2>
    <form action="/decrypt_upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file"><br><br>
        <button type="submit">Decrypt File</button>
    </form>
    
    <h2>View Stored Messages</h2>
    <p><a href="/view_messages">Click here to view encrypted messages</a></p>
    """


# API: peers send encrypted messages here
@app.route("/api/send_message", methods=["POST"])
def send_message_api():
    data = request.json

    sender = data.get("sender")
    receiver = data.get("receiver")
    ciphertext = data.get("ciphertext")

    if not (sender and receiver and ciphertext):
        return jsonify({"error": "Missing fields"}), 400

    store_message(sender, receiver, ciphertext)

    return jsonify({"status": "stored"})


# Owner decrypts file manually (same as before)
@app.route("/decrypt_upload", methods=["POST"])
def decrypt_upload():
    uploaded = request.files["file"].read()
    plaintext = decrypt_bytes(uploaded)
    return f"<h2>Decrypted Message:</h2><pre>{plaintext}</pre>"


# Owner views encrypted messages stored in db
@app.route("/view_messages")
def view_messages():
    messages = fetch_all_messages()

    html = "<h1>Encrypted Messages</h1>"
    html += "<ul>"

    for m in messages:
        msg_id, sender, receiver, ciphertext, timestamp = m
        html += f"""
        <li>
            <b>ID:</b> {msg_id}<br>
            <b>From:</b> {sender}<br>
            <b>To:</b> {receiver}<br>
            <b>Timestamp:</b> {timestamp}<br>
            <pre>{ciphertext}</pre>
            <hr>
        </li>
        """

    html += "</ul>"
    return html


if __name__ == "__main__":
    app.run(debug=True)


# --- ADD THIS HOMEPAGE ROUTE ---
@app.route("/")
def home():
    return """
    <h1>Owner Decrypt Web Interface</h1>
    <p>Upload an encrypted file below:</p>
    <form action="/decrypt" method="post" enctype="multipart/form-data">
        <input type="file" name="file"><br><br>
        <button type="submit">Decrypt File</button>
    </form>
    """

# --- ENCRYPTED FILE ENDPOINT ---
@app.route("/encrypted_file")
def encrypted_file():
    return send_file("encrypted.bin", as_attachment=True)

# --- DECRYPT ENDPOINT ---
@app.route("/decrypt", methods=["POST"])
def decrypt():
    from decrypter import decrypt_bytes

    uploaded = request.files["file"].read()
    decrypted = decrypt_bytes(uploaded)

    return f"<h2>Decrypted Message:</h2><pre>{decrypted}</pre>"

if __name__ == "__main__":
    app.run(debug=True)


app = Flask(__name__)

messages = []

ADMIN_TOKEN = "B25X25kfq"  # change only once, use same in decryptor


@app.route("/api/messages", methods=["POST"])
def post_message():
    data = request.get_json()
    messages.append(data)
    return jsonify({"status": "ok"}), 200


@app.route("/api/messages", methods=["GET"])
def get_messages():
    token = request.args.get("admin_token")
    if token != ADMIN_TOKEN:
        return jsonify({"error": "unauthorized"}), 403
    return jsonify({"messages": messages}), 200  # ALWAYS return dict


if __name__ == "__main__":
    print("SERVER RUNNING on http://127.0.0.1:5000")
    app.run(debug=True)
