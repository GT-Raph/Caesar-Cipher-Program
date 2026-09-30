import base64
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from src.cipher_vault.app import VaultApp, main


class AppTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.app = VaultApp(self.page)
        self.app.picker = SimpleNamespace(pick_files=AsyncMock(), save_file=AsyncMock(return_value='saved'))
        self.app.password.value = self.app.confirm.value = 'test passphrase for vault'

    async def test_text_encryption_decryption_and_clear(self):
        app = self.app
        app.message.value = 'Hello café'
        await app.process()
        encrypted = app.result.value
        self.assertEqual(base64.b64decode(encrypted), app.result_data)
        app.operation.value = 'decrypt'
        app.message.value = encrypted
        app.changed()
        await app.process()
        self.assertEqual(app.result.value, 'Hello café')
        await app.clear()
        self.assertIsNone(app.result_data)
        self.assertEqual(app.password.value, '')
        self.assertTrue(app.save_button.disabled)

    async def test_wrong_password_clears_result(self):
        app = self.app
        app.message.value = 'secret'
        await app.process()
        app.message.value = app.result.value
        app.password.value = 'wrong'
        app.operation.value = 'decrypt'
        await app.process()
        self.assertIsNone(app.result_data)
        self.assertEqual(app.result.value, '')
        self.assertIn('Unable to decrypt', app.status.value)

    async def test_mobile_file_bytes_and_save(self):
        app = self.app
        app.input_kind.value = 'file'
        app.picker.pick_files.return_value = [SimpleNamespace(name='empty.bin', size=0, bytes=b'', path=None)]
        await app.pick_file()
        await app.process()
        self.assertIsNotNone(app.result_data)
        await app.save()
        app.picker.save_file.assert_awaited_once_with(file_name='empty.bin.cvlt', src_bytes=app.result_data)

    async def test_cancel_selection_and_failed_password_confirmation(self):
        app = self.app
        app.picker.pick_files.return_value = []
        await app.pick_file()
        self.assertIsNone(app.file_data)
        app.confirm.value = 'different'
        await app.process()
        self.assertIn('do not match', app.status.value)
        self.assertFalse(app.busy)

    async def test_hybrid_key_generation_and_text_round_trip(self):
        app = self.app
        app.method.value = 'hybrid'
        await app.generate()
        self.assertIsNotNone(app.generated_keys)
        private, public = app.generated_keys
        app.key_data = public
        app.message.value = 'hybrid test'
        await app.process()
        self.assertIn('Verify', app.status.value)
        app.verified.value = True
        await app.process()
        app.message.value = app.result.value
        app.operation.value = 'decrypt'
        app.key_data = private
        await app.process()
        self.assertEqual(app.result.value, 'hybrid test')

    def test_main_constructs_current_flet_controls(self):
        main(self.page)
        self.page.add.assert_called_once()
