import base64
import os
import struct
import unittest

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.cipher_vault import password_crypto, hybrid_crypto
from src.cipher_vault.passphrases import generate, validate_new


class PassphraseTests(unittest.TestCase):
    def test_rejects_obviously_predictable_new_secrets(self):
        for secret in ('short', 'a' * 20, 'passwordpassword', '123456789012345',
                       'correct horse battery staple', ' ' * 20):
            with self.subTest(secret=secret), self.assertRaises(ValueError):
                validate_new(secret)

    def test_generated_secrets_and_unicode(self):
        secrets = {generate() for _ in range(100)}
        self.assertEqual(len(secrets), 100)
        for secret in secrets:
            self.assertEqual(len(secret), 32)
            validate_new(secret)
        validate_new('Unusual café mountains sunrise 84')

    def test_existing_weak_password_file_still_decrypts(self):
        # Construct the unchanged v1 format without calling the stricter writer.
        secret = 'oldpassword'
        salt = os.urandom(16)
        header = password_crypto.MAGIC + struct.pack('>I', password_crypto.ITERATIONS) + salt
        token = Fernet(password_crypto.derive_key(secret, salt)).encrypt(header + b'legacy data')
        self.assertEqual(password_crypto.decrypt(header + token, secret), b'legacy data')

    def test_existing_weak_private_key_password_still_decrypts(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.BestAvailableEncryption(b'oldpassword'))
        public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
        self.assertEqual(hybrid_crypto.decrypt(hybrid_crypto.encrypt(b'legacy', public), private, 'oldpassword'), b'legacy')
