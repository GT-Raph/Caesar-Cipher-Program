import base64
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
import flet as ft

from src.cipher_vault.app import VaultApp, main


class AppTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.page = Mock()
        self.page.web = False
        self.page.platform = ft.PagePlatform.ANDROID
        self.app = VaultApp(self.page)
        self.app.confirm_discard = AsyncMock(return_value=True)
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

    async def test_input_edits_preserve_unsaved_result(self):
        app = self.app
        app.result_data = b'keep this'
        app.result.value = 'keep this'
        app.result_saved = False
        app.changed()
        self.assertEqual(app.result_data, b'keep this')
        self.assertFalse(app.save_button.disabled)
        app.confirm_discard.return_value = False
        await app.clear()
        self.assertEqual(app.result_data, b'keep this')
        await app.process()
        self.assertEqual(app.result_data, b'keep this')

    async def test_keys_remain_unsaved_until_both_exports_succeed(self):
        app = self.app
        app.generated_keys = (b'private', b'public')
        await app.save_public()
        self.assertTrue(app.unsaved)
        app.picker.save_file.return_value = None
        await app.save_private()
        self.assertTrue(app.unsaved)
        app.picker.save_file.return_value = 'saved'
        await app.save_private()
        self.assertFalse(app.unsaved)

    async def test_close_blocked_during_work_and_for_unsaved_result(self):
        app = self.app
        self.page.window.destroy = AsyncMock()
        event = SimpleNamespace(type=ft.WindowEventType.CLOSE)
        app.busy = True
        await app.close_window(event)
        self.page.window.destroy.assert_not_awaited()
        app.busy = False
        app.generated_keys = (b'private', b'public')
        app.confirm_discard.return_value = False
        await app.close_window(event)
        self.page.window.destroy.assert_not_awaited()

    def test_web_mode_refuses_to_handle_secrets(self):
        self.page.web = True
        main(self.page)
        self.assertIn('native local', self.page.add.call_args.args[0].value)

    async def test_empty_mobile_export_reaches_native_api(self):
        from src.cipher_vault.native_files import save_mobile_bytes
        picker = SimpleNamespace(save_file=AsyncMock(), _invoke_method=AsyncMock(return_value='saved'))
        self.assertEqual(await save_mobile_bytes(picker, 'empty.bin', b''), 'saved')
        self.assertEqual(picker._invoke_method.call_args.args[1]['src_bytes'], b'')
        picker.save_file.assert_not_awaited()
