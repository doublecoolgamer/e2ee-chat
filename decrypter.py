# decrypter.py

# decrypter.py
import os
import base64
import requests
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.fernet import Fernet


# =============================
#  FERNET ENCRYPT / DECRYPT
# =============================
# REPLACE THIS KEY WITH THE SAME KEY USED BY YOUR CLIENT
FERNET_KEY = b"Mu3B75Iog5qZDKkLT7xLOmFfAEPq6on8Hro8jccyfL4="
fernet = Fernet(FERNET_KEY)

def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt raw bytes using Fernet."""
    return fernet.encrypt(data)

def decrypt_bytes(data: bytes) -> bytes:
    """Decrypt raw bytes using Fernet."""
    return fernet.decrypt(data)


# =============================
#  RSA PRIVATE KEY LOADING
# =============================
def load_private_key(path="keys/owner_private.pem"):
    with open(path, "rb") as f:
        return load_pem_private_key(f.read(), password=None)


# =============================
#  AES-GCM DECRYPTION (Used by your peers)
# =============================
def decrypt_aes_key(enc_key_b64, private_key):
    enc_key = base64.b64decode(enc_key_b64)
    raw_key = private_key.decrypt(
        enc_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return raw_key

def decrypt_aes_gcm(ciphertext_b64, iv_b64, aes_key_bytes):
    ciphertext = base64.b64decode(ciphertext_b64)
    iv = base64.b64decode(iv_b64)

    # last 16 bytes are tag
    tag = ciphertext[-16:]
    ct = ciphertext[:-16]

    decryptor = Cipher(
        algorithms.AES(aes_key_bytes),
        modes.GCM(iv, tag)
    ).decryptor()

    plaintext = decryptor.update(ct) + decryptor.finalize()
    return plaintext.decode("utf-8")


# =============================
#  SERVER SETTINGS
# =============================
SERVER = "http://127.0.0.1:50871"  # CHANGE TO YOUR ACTUAL PORT
ADMIN_TOKEN = "B25X25kfq"          # Must match server EXACTLY


# =============================
#  FETCH MESSAGES FROM SERVER
# =============================
def fetch_messages():
    r = requests.get(
        f"{SERVER}/api/messages",
        params={"admin_token": ADMIN_TOKEN}
    )
    r.raise_for_status()
    data = r.json()

    if "messages" not in data:
        raise ValueError("Server did not return messages")

    return data["messages"]


# =============================
#  MAIN – DECRYPT STORED MESSAGES
# =============================
def main():
    print("\nConnecting to server…\n")

    private_key = load_private_key()
    messages = fetch_messages()

    if not messages:
        print("No messages found.")
        return

    print(f"Fetched {len(messages)} messages:\n")

    for m in messages:
        try:
            aes_key = decrypt_aes_key(m["encrypted_key"], private_key)
            plaintext = decrypt_aes_gcm(m["ciphertext"], m["iv"], aes_key)

            print(f"---- MESSAGE {m['id']} FROM {m['sender']} ----")
            print(plaintext)
            print()
        except Exception as e:
            print(f"Message {m['id']} failed: {e}")


if __name__ == "__main__":
    main()
