import json
import tempfile
from pathlib import Path
import unittest

from src.cipher_vault.hybrid_crypto import CryptoError, decrypt, encrypt, generate_keypair


class HybridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'a long test passphrase'
        cls.private, cls.public = generate_keypair(cls.password)
        cls.other_private, _ = generate_keypair(cls.password)

    def test_binary_round_trip_and_fresh_randomness(self):
        data = bytes(range(256)) * 4096
        first = encrypt(data, self.public)
        second = encrypt(data, self.public)
        self.assertNotEqual(first, second)
        self.assertEqual(decrypt(first, self.private, self.password), data)

    def test_empty_file(self):
        self.assertEqual(decrypt(encrypt(b'', self.public), self.private, self.password), b'')

    def test_wrong_key_and_password(self):
        payload = encrypt(b'secret', self.public)
        for key, password in [(self.other_private, self.password), (self.private, 'wrong')]:
            with self.subTest(password=password), self.assertRaises(CryptoError):
                decrypt(payload, key, password)

    def test_tamper_every_envelope_field(self):
        payload = json.loads(encrypt(b'secret', self.public))
        for field in payload:
            changed = dict(payload)
            if field == 'version':
                changed[field] = 2
            else:
                value = changed[field]
                changed[field] = ('A' if value[0] != 'A' else 'B') + value[1:]
            with self.subTest(field=field), self.assertRaises(CryptoError):
                decrypt(json.dumps(changed).encode(), self.private, self.password)

    def test_malformed_envelopes(self):
        for payload in (b'{}', b'[]', b'null', b'not json', b'{"version":1,"version":1}', b'\xff'):
            with self.subTest(payload=payload), self.assertRaises(CryptoError):
                decrypt(payload, self.private, self.password)

    def test_private_key_is_encrypted(self):
        self.assertIn(b'BEGIN ENCRYPTED PRIVATE KEY', self.private)
        with self.assertRaises(CryptoError):
            generate_keypair('short')
        with self.assertRaises(CryptoError):
            generate_keypair('a' * 1024)
        with self.assertRaises(CryptoError):
            encrypt(b'text', self.private)

if __name__ == '__main__':
    unittest.main()
