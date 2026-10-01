"""Adversarial checks using synthetic data and isolated temporary directories."""

import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from src.cipher_vault import password_crypto as password
from src.cipher_vault import hybrid_crypto as hybrid
from src.cipher_vault.storage import export_new


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.passphrase = 'Synthetic adversarial test password'
        cls.private, cls.public = hybrid.generate_keypair(cls.passphrase)
        cls.hybrid_payload = hybrid.encrypt(b'authentication test', cls.public)
        cls.password_payload = password.encrypt(b'authentication test', cls.passphrase)

    def test_200_random_inputs_fail_without_kdf_or_key_loading(self):
        generator = random.Random(87123)
        with patch.object(password, 'derive_key') as derive, \
                patch.object(hybrid.serialization, 'load_pem_private_key') as load:
            for index in range(200):
                data = generator.randbytes(generator.randrange(0, 512))
                with self.subTest(case=index):
                    with self.assertRaises(password.EncryptionError):
                        password.decrypt(data, self.passphrase)
                    with self.assertRaises(hybrid.CryptoError):
                        hybrid.decrypt(data, self.private, self.passphrase)
            derive.assert_not_called()
            load.assert_not_called()

    def test_password_truncations_are_rejected(self):
        for length in (0, 4, 5, 8, 24, 25, 30, len(self.password_payload) - 4):
            with self.subTest(length=length), self.assertRaises(password.EncryptionError):
                password.decrypt(self.password_payload[:length], self.passphrase)

    def test_password_token_components_authenticate(self):
        header = self.password_payload[:password.HEADER_SIZE]
        token = base64.urlsafe_b64decode(self.password_payload[password.HEADER_SIZE:])
        # Fernet version, timestamp, IV, ciphertext, and HMAC.
        for offset in (0, 1, 9, 25, len(token) - 1):
            damaged = bytearray(token)
            damaged[offset] ^= 1
            payload = header + base64.urlsafe_b64encode(damaged)
            with self.subTest(offset=offset), self.assertRaises(password.EncryptionError):
                password.decrypt(payload, self.passphrase)

    def test_hybrid_nonce_wrapped_key_ciphertext_and_tag_authenticate(self):
        original = json.loads(self.hybrid_payload)
        for field, offset in [('nonce', 0), ('wrapped_key', 10), ('ciphertext', 0), ('ciphertext', -1)]:
            envelope = dict(original)
            data = bytearray(base64.b64decode(envelope[field]))
            data[offset] ^= 1
            envelope[field] = base64.b64encode(data).decode()
            with self.subTest(field=field, offset=offset), self.assertRaises(hybrid.CryptoError):
                hybrid.decrypt(json.dumps(envelope).encode(), self.private, self.passphrase)

    def test_json_type_confusion_and_extra_fields_rejected(self):
        original = json.loads(self.hybrid_payload)
        for field in original:
            for value in (None, [], {}, True, 1.0):
                envelope = dict(original)
                envelope[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(hybrid.CryptoError):
                    hybrid.decrypt(json.dumps(envelope).encode(), self.private, self.passphrase)
        original['extra'] = 'unexpected'
        with self.assertRaises(hybrid.CryptoError):
            hybrid.decrypt(json.dumps(original).encode(), self.private, self.passphrase)

    def test_weak_and_wrong_algorithm_public_keys_rejected(self):
        for key in (rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key(),
                    ed25519.Ed25519PrivateKey.generate().public_key()):
            pem = key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            with self.assertRaises(hybrid.CryptoError):
                hybrid.encrypt(b'synthetic', pem)

    def test_actual_password_file_limit_round_trip(self):
        data = b'\xa5' * password.MAX_DATA
        encrypted = password.encrypt(data, self.passphrase)
        self.assertLessEqual(len(encrypted), password.MAX_ENVELOPE)
        self.assertEqual(password.decrypt(encrypted, self.passphrase), data)
        with patch.object(password, 'derive_key') as derive:
            with self.assertRaises(password.EncryptionError):
                password.encrypt(data + b'x', self.passphrase)
            derive.assert_not_called()

    def test_racing_exports_never_mix_or_overwrite_content(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'result'
            values = [b'A' * 8192, b'B' * 8192]

            def attempt(data):
                try:
                    export_new(target, data)
                    return 'saved'
                except FileExistsError:
                    return 'rejected'

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(attempt, values))
            self.assertCountEqual(results, ['saved', 'rejected'])
            self.assertIn(target.read_bytes(), values)
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_unsupported_filesystem_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'result'
            with patch('src.cipher_vault.storage.os.link', side_effect=OSError('unsupported filesystem')):
                with self.assertRaises(OSError):
                    export_new(target, b'synthetic plaintext')
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])
