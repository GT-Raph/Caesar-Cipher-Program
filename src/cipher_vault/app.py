"""Responsive Flet UI. Cryptographic operations run outside the UI event loop."""

import asyncio
import base64
import binascii

import flet as ft

from . import password_crypto as password_engine
from . import hybrid_crypto as hybrid_engine
from .storage import export_new, read_bounded
from .native_files import save_mobile_bytes


class VaultApp:
    def __init__(self, page):
        self.page = page
        self.file_data = None
        self.file_name = None
        self.key_data = None
        self.generated_keys = None
        self.result_data = None
        self.result_name = 'encrypted.cvlt'
        self.busy = False
        self.result_saved = True
        self.saved_keys = set()
        self.confirming = False
        self.picker = ft.FilePicker()
        self.method = ft.Dropdown(label='Protection', value='password', options=[
            ft.DropdownOption('password', 'Password'), ft.DropdownOption('hybrid', 'Public key (AES + RSA)')], on_select=self.changed)
        self.operation = ft.Dropdown(label='Operation', value='encrypt', options=[
            ft.DropdownOption('encrypt', 'Encrypt'), ft.DropdownOption('decrypt', 'Decrypt')], on_select=self.changed)
        self.input_kind = ft.Dropdown(label='Input', value='text', options=[
            ft.DropdownOption('text', 'Text'), ft.DropdownOption('file', 'File')], on_select=self.changed)
        self.password = ft.TextField(label='Passphrase', password=True, can_reveal_password=True, on_change=self.changed)
        self.confirm = ft.TextField(label='Confirm passphrase', password=True, can_reveal_password=True, on_change=self.changed)
        self.message = ft.TextField(label='Message or encrypted text', multiline=True, min_lines=5, max_lines=9, on_change=self.changed)
        self.file_label = ft.Text('No file selected.')
        self.key_label = ft.Text('No key selected.', selectable=True)
        self.verified = ft.Checkbox(label='I verified this public-key fingerprint with its owner.', value=False, on_change=self.changed)
        self.pick_button = ft.Button('Choose file', icon=ft.Icons.ATTACH_FILE, on_click=self.pick_file)
        self.key_button = ft.Button('Choose PEM key', on_click=self.pick_key)
        self.run_button = ft.Button('Encrypt', icon=ft.Icons.LOCK_OUTLINE, on_click=self.process, height=48)
        self.save_button = ft.Button('Save result', icon=ft.Icons.SAVE_OUTLINED, on_click=self.save, disabled=True)
        self.clear_button = ft.TextButton('Clear workspace', on_click=self.clear)
        self.generate_button = ft.Button('Generate RSA key pair', on_click=self.generate)
        self.public_button = ft.Button('Save public key', on_click=self.save_public, disabled=True)
        self.private_button = ft.Button('Save private key', on_click=self.save_private, disabled=True)
        self.result = ft.TextField(label='Result', multiline=True, min_lines=5, max_lines=9, read_only=True)
        self.status = ft.Text('Ready. Your data stays in this app; nothing is uploaded.', selectable=True)
        self.progress = ft.ProgressBar(visible=False)
        self.file_area = ft.Column([self.pick_button, self.file_label], visible=False)
        self.key_area = ft.Column([self.key_button, self.key_label, self.verified], visible=False)
        self.key_tools = ft.ExpansionTile(title=ft.Text('Create a public/private key pair'), controls=[
            ft.Text('Use and confirm the passphrase above. Save both keys before clearing or closing. Share only the public key.'),
            self.generate_button, ft.Row([self.public_button, self.private_button], wrap=True)], visible=False)
        self.form = ft.Column([
            ft.ResponsiveRow([ft.Container(self.method, col={'xs':12, 'md':6}),
                              ft.Container(self.operation, col={'xs':6, 'md':3}),
                              ft.Container(self.input_kind, col={'xs':6, 'md':3})]),
            self.message, self.file_area, self.key_area, self.password, self.confirm, self.key_tools,
            ft.Row([self.run_button, self.clear_button], wrap=True),
        ], spacing=16)
        self.view = ft.SafeArea(ft.Container(ft.Column([
            ft.Text('CIPHER VAULT', size=14, weight=ft.FontWeight.BOLD, color='#0f766e'),
            ft.Text('Keep your words yours.', size=32, weight=ft.FontWeight.BOLD),
            ft.Text('Encrypt messages and files with a password or a recipient’s public key.'),
            ft.Container(self.form, padding=20, bgcolor='#ffffff', border_radius=16),
            self.progress, self.status,
            ft.Container(ft.Column([ft.Text('Your result', size=20, weight=ft.FontWeight.BOLD),
                                   self.result, self.save_button], spacing=12), padding=20, bgcolor='#ffffff', border_radius=16),
            ft.Text('Save results before closing. Forgotten passphrases cannot be recovered. Clear the workspace when finished.', color='#475569'),
        ], spacing=18, scroll=ft.ScrollMode.AUTO), padding=20, expand=True), expand=True)

    def changed(self, event=None):
        self.save_button.disabled = self.result_data is None
        hybrid = self.method.value == 'hybrid'
        encrypting = self.operation.value == 'encrypt'
        self.message.visible = self.input_kind.value == 'text'
        self.file_area.visible = not self.message.visible
        self.key_area.visible = hybrid
        self.key_tools.visible = hybrid
        self.verified.visible = hybrid and encrypting
        self.password.visible = not hybrid or not encrypting or self.key_tools.visible
        self.password.label = 'Private-key passphrase (for decryption / key generation)' if hybrid else 'Passphrase'
        self.confirm.visible = encrypting or hybrid
        self.run_button.content = 'Encrypt' if encrypting else 'Decrypt'
        self.status.value = ('Inputs changed. The previous result is still available to save.'
                             if self.result_data is not None else 'Ready.')
        self.page.update()

    @property
    def desktop(self):
        return self.page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX)

    @property
    def unsaved(self):
        return ((self.result_data is not None and not self.result_saved)
                or (self.generated_keys is not None and self.saved_keys != {0, 1}))

    async def confirm_discard(self, message):
        if self.confirming:
            return False
        self.confirming = True
        answer = asyncio.get_running_loop().create_future()

        def finish(value):
            if not answer.done():
                answer.set_result(value)

        def respond(value):
            def handler(event):
                finish(value)
                self.page.pop_dialog()
            return handler

        dialog = ft.AlertDialog(modal=True, title=ft.Text('Discard unsaved work?'),
            content=ft.Text(message), actions=[ft.TextButton('Keep working', on_click=respond(False)),
                                             ft.TextButton('Discard', on_click=respond(True))],
            on_dismiss=lambda event: finish(False))
        self.page.show_dialog(dialog)
        try:
            return await answer
        finally:
            self.confirming = False

    async def close_window(self, event):
        if event.type != ft.WindowEventType.CLOSE:
            return
        if self.busy:
            self.status.value = 'Wait for the current operation to finish before closing.'
            self.page.update()
            return
        if self.unsaved and not await self.confirm_discard('Your unsaved result or generated keys will be lost.'):
            return
        await self.page.window.destroy()

    async def guarded(self, action):
        if self.busy or self.confirming:
            return
        self.busy = True
        self.form.disabled = True
        self.save_button.disabled = True
        self.progress.visible = True
        self.page.update()
        try:
            await action()
        except (ValueError, OSError, binascii.Error) as error:
            self.status.value = str(error)
        except Exception:
            # Do not surface runtime exception details that could contain user data.
            self.status.value = 'The operation could not finish. Try again or restart the app.'
        finally:
            self.busy = False
            self.form.disabled = False
            self.progress.visible = False
            self.save_button.disabled = self.result_data is None
            self.page.update()

    async def selected_bytes(self, limit):
        files = await self.picker.pick_files(allow_multiple=False, with_data=not self.desktop)
        if not files:
            return None
        selected = files[0]
        if selected.size > limit:
            raise ValueError(f'This file exceeds the {limit:,}-byte limit.')
        data = (await asyncio.to_thread(read_bounded, selected.path, limit)
                if self.desktop and selected.path else selected.bytes)
        if data is None:
            raise ValueError('The file provider did not return readable data. Choose a locally available file.')
        if len(data) > limit:
            raise ValueError('The selected file is too large.')
        return selected.name, data

    async def pick_file(self, event=None):
        async def work():
            selected = await self.selected_bytes(password_engine.MAX_ENVELOPE)
            if selected is not None:
                self.file_name, self.file_data = selected
                self.file_label.value = f'{self.file_name} · {len(self.file_data):,} bytes'
                self.changed()
        await self.guarded(work)

    async def pick_key(self, event=None):
        async def work():
            selected = await self.selected_bytes(32768)
            if selected is not None:
                name, data = selected
                self.key_data = None
                self.verified.value = False
                self.key_label.value = 'No key selected.'
                self.changed()
                if self.operation.value == 'encrypt':
                    key = hybrid_engine.public_key(data)
                    self.key_label.value = 'SHA-256 fingerprint:\n' + hybrid_engine.fingerprint(key)
                else:
                    self.key_label.value = f'Private key: {name}'
                self.key_data = data
        await self.guarded(work)

    async def process(self, event=None):
        async def work():
            if self.result_data is not None and not self.result_saved:
                if not await self.confirm_discard('Running again will replace the unsaved result. Save it first to keep it.'):
                    return
            self.result_data = None
            self.result.value = ''
            encrypting = self.operation.value == 'encrypt'
            hybrid = self.method.value == 'hybrid'
            input_kind = self.input_kind.value
            password = self.password.value or ''
            if encrypting and not hybrid and password != self.confirm.value:
                raise ValueError('The passphrases do not match.')
            if input_kind == 'file':
                if self.file_data is None:
                    raise ValueError('Choose a file first.')
                data = self.file_data
                name = self.file_name
            else:
                text = self.message.value or ''
                if len(text) > (250_000 if encrypting else 2_000_000):
                    raise ValueError('This message is too large for text mode. Use file mode instead.')
                data = text.encode('utf-8') if encrypting else base64.b64decode(text.strip(), validate=True)
                name = 'message.txt'
            if encrypting and len(data) > password_engine.MAX_DATA:
                raise ValueError('Files must be 16 MiB or smaller.')
            self.status.value = 'Encrypting…' if encrypting else 'Decrypting and checking authenticity…'
            self.page.update()
            if hybrid:
                if self.key_data is None:
                    raise ValueError('Choose the recipient public key or your private key first.')
                if encrypting and not self.verified.value:
                    raise ValueError('Verify the public-key fingerprint before encrypting.')
                if encrypting:
                    output = await asyncio.to_thread(hybrid_engine.encrypt, data, self.key_data)
                else:
                    output = await asyncio.to_thread(hybrid_engine.decrypt, data, self.key_data, password)
                extension = '.cse'
            else:
                fn = password_engine.encrypt if encrypting else password_engine.decrypt
                output = await asyncio.to_thread(fn, data, password)
                extension = '.cvlt'
            self.result_data = output
            self.result_saved = False
            self.result_name = name + extension if encrypting else 'decrypted-' + name.removesuffix('.cvlt').removesuffix('.cse')
            if input_kind == 'text':
                if encrypting:
                    self.result.value = base64.b64encode(output).decode('ascii')
                else:
                    try:
                        self.result.value = output.decode('utf-8')
                    except UnicodeDecodeError:
                        self.result.value = 'Binary result. Save it to a file.'
            else:
                self.result.value = f'{len(output):,} bytes ready to save.'
            self.status.value = 'Complete. Save your result before closing or changing inputs.'
        await self.guarded(work)

    async def save(self, event=None):
        async def work():
            if self.result_data is not None:
                path = await self.export(self.result_name, self.result_data)
                if path:
                    self.result_saved = True
                self.status.value = 'Result saved.' if path else 'Save cancelled. The result is still available.'
        await self.guarded(work)

    async def export(self, name, data):
        if self.desktop:
            path = await self.picker.save_file(file_name=name, dialog_title='Save to a new filename')
            if path:
                try:
                    await asyncio.to_thread(export_new, path, data)
                except FileExistsError as error:
                    raise ValueError('That file already exists. Choose a new filename to protect your original.') from error
            return path
        return await save_mobile_bytes(self.picker, name, data)

    async def generate(self, event=None):
        async def work():
            if self.generated_keys is not None:
                raise ValueError('Save your current key pair, then clear the workspace before generating another.')
            password = self.password.value or ''
            if password != self.confirm.value:
                raise ValueError('Confirm the matching private-key passphrase above.')
            self.generated_keys = await asyncio.to_thread(hybrid_engine.generate_keypair, password)
            self.saved_keys.clear()
            self.private_button.disabled = self.public_button.disabled = False
            self.status.value = 'Key pair ready. Save BOTH keys. Share only the public key.'
        await self.guarded(work)

    async def save_public(self, event=None):
        await self.export_key(1, 'public.pem')

    async def save_private(self, event=None):
        await self.export_key(0, 'private.pem')

    async def export_key(self, index, name):
        async def work():
            if self.generated_keys is not None:
                path = await self.export(name, self.generated_keys[index])
                if path:
                    self.saved_keys.add(index)
                self.status.value = f'Saved {name}.' if path else 'Save cancelled. Keys are still available.'
        await self.guarded(work)

    async def clear(self, event=None):
        if self.busy or self.confirming:
            return
        if self.unsaved and not await self.confirm_discard('Clearing will discard unsaved results and generated keys.'):
            return
        self.file_data = self.key_data = self.generated_keys = self.result_data = None
        self.file_name = None
        self.password.value = self.confirm.value = self.message.value = ''
        self.file_label.value = 'No file selected.'
        self.key_label.value = 'No key selected.'
        self.verified.value = False
        self.public_button.disabled = self.private_button.disabled = True
        self.result.value = ''
        self.result_saved = True
        self.saved_keys.clear()
        self.changed()
        self.status.value = 'Workspace cleared.'
        self.page.update()


def main(page: ft.Page):
    if page.web:
        page.add(ft.Text('Cipher Vault requires native local execution. Launch the desktop or mobile app.'))
        return
    page.title = 'Cipher Vault'
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed='#0f766e', font_family='Segoe UI')
    page.bgcolor = '#f1f5f9'
    page.padding = 0
    page.window.width = 920
    page.window.height = 860
    app = VaultApp(page)
    if app.desktop:
        page.window.prevent_close = True
        page.window.on_event = app.close_window
    page.add(app.view)
