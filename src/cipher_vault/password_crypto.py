"""Password encryption with a bounded, versioned, self-contained envelope."""

import base64
import os
import struct

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .passphrases import validate_new

MAGIC = b'CVLT\x01'
ITERATIONS = 1_200_000
SALT_SIZE = 16
MAX_DATA = 16 * 1024 * 1024
MAX_ENVELOPE = 24 * 1024 * 1024
HEADER_SIZE = len(MAGIC) + 4 + SALT_SIZE


class EncryptionError(ValueError):
    """A user-recoverable encryption or authentication failure."""


def derive_key(password: str, salt: bytes) -> bytes:
    if not password or len(password.encode('utf-8')) > 1024:
        raise EncryptionError('Enter a password of 1–1024 UTF-8 bytes.')
    if len(salt) != SALT_SIZE:
        raise EncryptionError('Invalid salt length.')
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))


def encrypt(data: bytes, password: str) -> bytes:
    try:
        validate_new(password)
    except ValueError as error:
        raise EncryptionError(str(error)) from error
    if len(data) > MAX_DATA:
        raise EncryptionError('Files must be 16 MiB or smaller.')
    salt = os.urandom(SALT_SIZE)
    header = MAGIC + struct.pack('>I', ITERATIONS) + salt
    # Fernet authenticates an inner copy of the header as well as the payload.
    token = Fernet(derive_key(password, salt)).encrypt(header + data)
    return header + token


def decrypt(payload: bytes, password: str) -> bytes:
    if len(payload) > MAX_ENVELOPE or len(payload) <= HEADER_SIZE or not payload.startswith(MAGIC):
        raise EncryptionError('This is not a supported Cipher Vault file.')
    header = payload[:HEADER_SIZE]
    iterations = struct.unpack('>I', header[len(MAGIC):len(MAGIC) + 4])[0]
    # Never accept attacker-controlled KDF work factors.
    if iterations != ITERATIONS:
        raise EncryptionError('Unsupported encryption parameters.')
    try:
        token = payload[HEADER_SIZE:]
        if base64.urlsafe_b64encode(base64.b64decode(token, altchars=b'-_', validate=True)) != token:
            raise InvalidToken
        plain = Fernet(derive_key(password, header[-SALT_SIZE:])).decrypt(token)
        if not plain.startswith(header) or len(plain) - HEADER_SIZE > MAX_DATA:
            raise InvalidToken
    except (InvalidToken, ValueError) as error:
        raise EncryptionError('Unable to decrypt. The password is incorrect or the file has been changed.') from error
    return plain[HEADER_SIZE:]
