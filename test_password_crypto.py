import unittest
from unittest.mock import patch

from src.cipher_vault import password_crypto as crypto


class PasswordTests(unittest.TestCase):
    password = 'correct horse battery staple'

    def test_binary_empty_and_unicode_round_trips(self):
        for data in (b'', bytes(range(256)), 'Hello café 中文'.encode()):
            with self.subTest(data=data):
                self.assertEqual(crypto.decrypt(crypto.encrypt(data, self.password), self.password), data)

    def test_randomized_encryption(self):
        self.assertNotEqual(crypto.encrypt(b'same', self.password), crypto.encrypt(b'same', self.password))

    def test_tampering_and_wrong_password(self):
        payload = crypto.encrypt(b'secret', self.password)
        for index in (0, 5, 10, crypto.HEADER_SIZE + 20, len(payload) - 8):
            changed = bytearray(payload)
            changed[index] ^= 1
            with self.subTest(index=index), self.assertRaises(crypto.EncryptionError):
                crypto.decrypt(bytes(changed), self.password)
        with self.assertRaises(crypto.EncryptionError):
            crypto.decrypt(payload, 'incorrect password')
        for changed in (payload + b'!', payload[:-1]):
            with self.assertRaises(crypto.EncryptionError):
                crypto.decrypt(changed, self.password)

    def test_bad_header_rejected_before_kdf(self):
        with patch.object(crypto, 'derive_key') as derive:
            for payload in (b'', b'garbage', crypto.MAGIC + b'\xff' * 200):
                with self.assertRaises(crypto.EncryptionError):
                    crypto.decrypt(payload, self.password)
            derive.assert_not_called()

    def test_password_and_size_limits(self):
        for password in ('', 'short', 'x' * 1025):
            with self.assertRaises(crypto.EncryptionError):
                crypto.encrypt(b'text', password)
        with patch.object(crypto, 'MAX_DATA', 3), self.assertRaises(crypto.EncryptionError):
            crypto.encrypt(b'long', self.password)
