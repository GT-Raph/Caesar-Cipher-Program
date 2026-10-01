"""Versioned AES-256-GCM envelopes; retains the original format for compatibility."""

import base64
import binascii
import hashlib
import json
import os

from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .passphrases import validate_new

MAX_DATA = 64 * 1024 * 1024
MAX_ENVELOPE = 90 * 1024 * 1024
SUITE = 'AES-256-GCM+RSA-OAEP-SHA256'
FIELDS = {'version', 'suite', 'recipient', 'wrapped_key', 'nonce', 'ciphertext'}


class CryptoError(ValueError):
    """Invalid keys, envelopes, or failed authentication."""


def oaep():
    return padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                        algorithm=hashes.SHA256(), label=b'CaesarStudio/v1')


def public_key(pem):
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError, UnsupportedAlgorithm) as error:
        raise CryptoError('Choose a valid RSA public key in PEM format.') from error
    if not isinstance(key, rsa.RSAPublicKey) or not 3072 <= key.key_size <= 8192:
        raise CryptoError('RSA keys must be between 3072 and 8192 bits.')
    return key


def fingerprint(key):
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(der).hexdigest()


def generate_keypair(password):
    try:
        validate_new(password, max_bytes=1023)
    except ValueError as error:
        raise CryptoError(str(error)) from error
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.BestAvailableEncryption(password.encode('utf-8')))
    public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                           serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public


def encode(value):
    return base64.b64encode(value).decode('ascii')


def aad(envelope):
    return json.dumps({key: envelope[key] for key in ('version', 'suite', 'recipient', 'wrapped_key', 'nonce')},
                      sort_keys=True, separators=(',', ':')).encode('ascii')


def encrypt(data, public_pem):
    if len(data) > MAX_DATA:
        raise CryptoError('Files are limited to 64 MiB.')
    recipient = public_key(public_pem)
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    envelope = dict(version=1, suite=SUITE, recipient=fingerprint(recipient),
                    wrapped_key=encode(recipient.encrypt(key, oaep())), nonce=encode(nonce))
    envelope['ciphertext'] = encode(AESGCM(key).encrypt(nonce, data, aad(envelope)))
    return json.dumps(envelope, sort_keys=True, separators=(',', ':')).encode('ascii')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CryptoError('Duplicate envelope field.')
        result[key] = value
    return result


def decrypt(payload, private_pem, password):
    if len(payload) > MAX_ENVELOPE:
        raise CryptoError('Encrypted file exceeds the supported size.')
    try:
        envelope = json.loads(payload, object_pairs_hook=unique_object)
        if not isinstance(envelope, dict) or set(envelope) != FIELDS:
            raise ValueError('fields')
        if type(envelope['version']) is not int or envelope['version'] != 1 or envelope['suite'] != SUITE:
            raise ValueError('version')
        if any(not isinstance(envelope[key], str) for key in FIELDS - {'version'}):
            raise ValueError('types')
        nonce = base64.b64decode(envelope['nonce'], validate=True)
        wrapped = base64.b64decode(envelope['wrapped_key'], validate=True)
        ciphertext = base64.b64decode(envelope['ciphertext'], validate=True)
        if len(nonce) != 12 or not 16 <= len(ciphertext) <= MAX_DATA + 16:
            raise ValueError('length')
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, binascii.Error) as error:
        raise CryptoError('Invalid or unsupported encrypted file.') from error
    try:
        key = serialization.load_pem_private_key(private_pem, password=password.encode('utf-8'))
        if not isinstance(key, rsa.RSAPrivateKey) or not 3072 <= key.key_size <= 8192:
            raise ValueError('key type')
        if fingerprint(key.public_key()) != envelope['recipient'] or len(wrapped) != key.key_size // 8:
            raise ValueError('recipient')
        aes_key = key.decrypt(wrapped, oaep())
        if len(aes_key) != 32:
            raise ValueError('AES key length')
        return AESGCM(aes_key).decrypt(nonce, ciphertext, aad(envelope))
    except (ValueError, TypeError, InvalidTag, UnsupportedAlgorithm) as error:
        raise CryptoError('Decryption failed. Check the private key and passphrase; the file may have been changed.') from error
