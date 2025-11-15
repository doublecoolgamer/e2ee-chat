import os
import base64
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet

FERNET_KEY = os.environ.get("FERNET_KEY").encode()  # must be set in env
cipher = Fernet(FERNET_KEY)

def encrypt_bytes(data: bytes) -> bytes:
    return cipher.encrypt(data)

def decrypt_bytes(data: bytes) -> bytes:
    return cipher.decrypt(data)

def load_private_key(path="keys/owner_private.pem"):
    with open(path, "rb") as f:
        return load_pem_private_key(f.read(), password=None)

def load_public_key(path="keys/owner_public.pem"):
    with open(path, "rb") as f:
        return load_pem_public_key(f.read())

def encrypt_with_rsa(message: str, public_key):
    return public_key.encrypt(
        message.encode(),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )

def decrypt_with_rsa(ciphertext: bytes, private_key):
    return private_key.decrypt(
        ciphertext,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    ).decode()
