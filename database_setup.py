import sqlite3

conn = sqlite3.connect("messages.db")
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

print("Database initialized.")
