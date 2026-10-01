"""Offline packaged-runtime smoke test using synthetic data only."""

import platform
import sys

import cryptography
from cryptography.hazmat.backends import default_backend
from flet.version import flet_version

from . import password_crypto, hybrid_crypto


def run():
    password = 'Synthetic runtime check only'
    data = bytes(range(256)) + b'\x00Cipher Vault runtime check'
    payload = password_crypto.encrypt(data, password)
    if password_crypto.decrypt(payload, password) != data:
        raise RuntimeError('Password encryption round trip failed.')
    try:
        password_crypto.decrypt(payload, 'incorrect password')
    except password_crypto.EncryptionError:
        pass
    else:
        raise RuntimeError('Incorrect password was accepted.')
    private, public = hybrid_crypto.generate_keypair(password)
    envelope = hybrid_crypto.encrypt(data, public)
    if hybrid_crypto.decrypt(envelope, private, password) != data:
        raise RuntimeError('Hybrid encryption round trip failed.')
    return {
        'status': 'passed', 'python': sys.version.split()[0],
        'platform': platform.platform(), 'cryptography': cryptography.__version__,
        'flet': flet_version, 'openssl': default_backend().openssl_version_text(),
        'checks': ['password binary round trip', 'wrong password rejection', 'RSA/AES binary round trip'],
        'scope': 'Cryptographic runtime only; does not verify native UI, file pickers, or signing.',
    }
