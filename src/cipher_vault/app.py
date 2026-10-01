"""Responsive Flet UI. Cryptographic operations run outside the UI event loop."""

import asyncio
import base64
import binascii
import hmac
import re

import flet as ft

from . import password_crypto as password_engine
from . import hybrid_crypto as hybrid_engine
from .storage import export_new, read_bounded
from .native_files import save_mobile_bytes
from .passphrases import generate as generate_passphrase


# Vault steel and ink. Brass is reserved for the lock mark and progress.
STEEL = '#E4E7EC'
PAPER = '#FFFFFF'
WELL = '#F3F5F8'
INK = '#172033'
SLATE = '#4A5468'
LINE = '#C9CFD9'
HAIRLINE = '#D8DDE5'
BRASS = '#8C6A1A'
BRASS_TINT = '#F4ECD8'
SEALED = '#141C2E'
SEALED_TEXT = '#D5DDEC'
SEALED_MUTED = '#9AA6BF'
SEALED_LINE = '#2C3754'
DANGER = '#A8231C'

TONES = {
    'info': (ft.Icons.INFO_OUTLINE, SLATE, '#EEF1F5'),
    'success': (ft.Icons.CHECK_CIRCLE_OUTLINE, '#1D6A45', '#E7F3EC'),
    'warning': (ft.Icons.WARNING_AMBER_ROUNDED, '#7A5410', '#FBF3E2'),
    'error': (ft.Icons.ERROR_OUTLINE, DANGER, '#FBECEB'),
}

# Result panel copy and surface per state: (icon, title, note, sealed surface, monospace).
RESULT_STATES = {
    'empty': (ft.Icons.NOTES, 'Result', 'Encrypt or decrypt something and the output appears here. '
              'Nothing is written to disk until you choose Save result.', False, False),
    'sealed': (ft.Icons.LOCK, 'Encrypted text',
               'Copy the whole value to share it, or save it and reopen the file in File mode.', True, True),
    'plain': (ft.Icons.LOCK_OPEN_OUTLINED, 'Decrypted message',
              'Authenticity checked. Save it or clear the workspace when you are done.', False, False),
    'binary': (ft.Icons.LOCK_OPEN_OUTLINED, 'Decrypted data',
               'This result is not text. Save it to a file to open it.', False, False),
    'file-encrypted': (ft.Icons.LOCK, 'Encrypted file ready', 'Save it to a new filename.', True, True),
    'file-decrypted': (ft.Icons.LOCK_OPEN_OUTLINED, 'Decrypted file ready',
                       'Save it to a new filename.', False, False),
}

STATE_EASE = ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC)
STATUS_EASE = ft.Animation(160, ft.AnimationCurve.EASE_OUT_CUBIC)


def mono_family(platform):
    return {ft.PagePlatform.WINDOWS: 'Consolas', ft.PagePlatform.MACOS: 'Menlo',
            ft.PagePlatform.IOS: 'Menlo'}.get(platform, 'monospace')


def button_style(bg=INK, fg=PAPER, side=None):
    return ft.ButtonStyle(
        bgcolor={ft.ControlState.DISABLED: '#DDE1E8', ft.ControlState.DEFAULT: bg},
        color={ft.ControlState.DISABLED: '#6B7488', ft.ControlState.DEFAULT: fg},
        icon_color={ft.ControlState.DISABLED: '#6B7488', ft.ControlState.DEFAULT: fg},
        side=side, elevation=0, shape=ft.RoundedRectangleBorder(radius=10),
        padding=ft.Padding.symmetric(horizontal=20, vertical=14))


def secondary_style():
    return button_style(PAPER, INK, ft.BorderSide(1, LINE))


def quiet_style(color=INK):
    return ft.ButtonStyle(color=color, icon_color=color, shape=ft.RoundedRectangleBorder(radius=10),
                          padding=ft.Padding.symmetric(horizontal=12, vertical=14))


SEGMENT_STYLE = ft.ButtonStyle(
    bgcolor={ft.ControlState.SELECTED: INK, ft.ControlState.DEFAULT: PAPER},
    color={ft.ControlState.SELECTED: PAPER, ft.ControlState.DEFAULT: INK},
    icon_color={ft.ControlState.SELECTED: PAPER, ft.ControlState.DEFAULT: SLATE},
    side=ft.BorderSide(1, LINE), shape=ft.RoundedRectangleBorder(radius=10),
    padding=ft.Padding.symmetric(horizontal=16, vertical=12))


def field(**kwargs):
    return ft.TextField(border_radius=10, border_color=LINE, focused_border_color=INK, focused_border_width=2,
                        filled=True, fill_color=PAPER, label_style=ft.TextStyle(color=SLATE),
                        text_style=ft.TextStyle(size=15, color=INK), **kwargs)


def caption(text):
    return ft.Text(text, size=13, weight=ft.FontWeight.W_600, color=SLATE)


class Choice:
    """Single-selection segmented control that exposes the selected value as `.value`."""

    def __init__(self, options, value, on_change):
        self.control = ft.SegmentedButton(
            segments=[ft.Segment(key, label=label, icon=icon) for key, label, icon in options],
            selected=[value], show_selected_icon=False, style=SEGMENT_STYLE, on_change=on_change)

    @property
    def value(self):
        return self.control.selected[0]

    @value.setter
    def value(self, value):
        self.control.selected = [value]


class VaultApp:
    def __init__(self, page):
        self.page = page
        self.mono = mono_family(page.platform)
        self.file_data = None
        self.file_name = None
        self.key_data = None
        self.generated_keys = None
        self.result_data = None
        self.result_kind = 'empty'
        self.result_name = 'encrypted.cvlt'
        self.busy = False
        self.result_saved = True
        self.saved_keys = set()
        self.confirming = False
        self.backgrounded = False
        self.generated_passphrase = None
        self.picker = ft.FilePicker()

        self.operation = Choice([('encrypt', 'Encrypt', ft.Icons.LOCK_OUTLINE),
                                 ('decrypt', 'Decrypt', ft.Icons.LOCK_OPEN_OUTLINED)], 'encrypt', self.changed)
        self.method = Choice([('password', 'Password', None), ('hybrid', 'Public key', None)], 'password', self.changed)
        self.input_kind = Choice([('text', 'Text', None), ('file', 'File', None)], 'text', self.changed)
        self.password = field(label='Passphrase', password=True, can_reveal_password=True, on_change=self.changed)
        self.confirm = field(label='Confirm passphrase', password=True, can_reveal_password=True, on_change=self.changed)
        self.message = field(label='Message', multiline=True, min_lines=6, max_lines=12, on_change=self.changed)
        self.file_label = ft.Text('No file selected.', color=SLATE, size=14)
        self.key_label = ft.Text('No key selected.', selectable=True, color=INK, size=13, font_family=self.mono)
        self.verified = ft.Checkbox(label='I verified this public-key fingerprint with its owner.', value=False,
                                    active_color=INK, on_change=self.changed)
        self.expected_fingerprint = field(label='Recipient fingerprint from a trusted channel',
            hint_text='Paste all 64 hexadecimal characters', on_change=self.changed)
        self.expected_fingerprint.text_style = ft.TextStyle(size=13, color=INK, font_family=self.mono)
        self.random_button = ft.TextButton('Generate strong passphrase', icon=ft.Icons.PASSWORD,
                                           style=quiet_style(), on_click=self.new_passphrase)
        self.passphrase_saved = ft.Checkbox(label='I stored the generated passphrase securely.', value=False,
                                            active_color=INK, visible=False)
        self.pick_button = ft.Button('Choose file', icon=ft.Icons.ATTACH_FILE, style=secondary_style(),
                                     on_click=self.pick_file)
        self.key_button = ft.Button('Choose PEM key', icon=ft.Icons.KEY_OUTLINED, style=secondary_style(),
                                    on_click=self.pick_key)
        self.run_button = ft.Button('Encrypt', icon=ft.Icons.LOCK_OUTLINE, style=button_style(), height=48,
                                    on_click=self.process)
        self.save_button = ft.Button('Save result', icon=ft.Icons.SAVE_OUTLINED, style=button_style(), height=48,
                                     on_click=self.save, disabled=True)
        self.clear_button = ft.TextButton('Clear workspace', style=quiet_style(SLATE), on_click=self.clear)
        self.generate_button = ft.Button('Generate RSA key pair', style=secondary_style(), on_click=self.generate)
        self.public_button = ft.Button('Save public key', style=secondary_style(), on_click=self.save_public,
                                       disabled=True)
        self.private_button = ft.Button('Save private key', style=secondary_style(), on_click=self.save_private,
                                        disabled=True)

        self.result = ft.TextField(multiline=True, min_lines=10, max_lines=16, read_only=True,
                                   border=ft.NoInputBorder(), content_padding=0)
        self.result_icon = ft.Icon(ft.Icons.NOTES, size=20)
        self.result_title = ft.Text('Result', size=17, weight=ft.FontWeight.W_600)
        self.result_note = ft.Text('', size=13)
        self.result_panel = ft.Container(ft.Column([
            ft.Row([self.result_icon, self.result_title], spacing=10),
            self.result_note, self.result, self.save_button,
        ], spacing=12), padding=24, border_radius=16, animate=STATE_EASE)

        self.status_icon = ft.Icon(ft.Icons.INFO_OUTLINE, size=18)
        self.status = ft.Text('', selectable=True, size=14, expand=True)
        self.status_bar = ft.Container(ft.Row([self.status_icon, self.status], spacing=10,
                                              vertical_alignment=ft.CrossAxisAlignment.START),
                                       padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                                       border_radius=10, animate=STATUS_EASE)
        self.progress = ft.ProgressBar(visible=False, color=BRASS, bgcolor=BRASS_TINT, bar_height=3, border_radius=2)

        self.file_area = ft.Row([self.pick_button, self.file_label], spacing=14, wrap=True, visible=False,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.key_area = ft.Container(ft.Column([
            caption('Key'),
            ft.Row([self.key_button], wrap=True), self.key_label,
            ft.Text('For encryption, get the fingerprint from the recipient separately, not from the key file.',
                    size=13, color=SLATE),
            self.expected_fingerprint, self.verified,
        ], spacing=12), padding=16, border_radius=12, bgcolor=WELL, border=ft.Border.all(1, HAIRLINE), visible=False)
        self.key_tools = ft.ExpansionTile(
            title=ft.Text('Create a public/private key pair', weight=ft.FontWeight.W_600, color=INK),
            subtitle=ft.Text('RSA-3072. The private key is encrypted with your passphrase.', size=13, color=SLATE),
            leading=ft.Icon(ft.Icons.KEY_OUTLINED, color=SLATE),
            bgcolor=WELL, collapsed_bgcolor=WELL, icon_color=INK, collapsed_icon_color=SLATE,
            shape=ft.RoundedRectangleBorder(radius=12), collapsed_shape=ft.RoundedRectangleBorder(radius=12),
            controls_padding=ft.Padding.only(left=16, right=16, bottom=16),
            expanded_cross_axis_alignment=ft.CrossAxisAlignment.START,
            controls=[ft.Column([
                ft.Text('Use and confirm the passphrase above. Save both keys before clearing or closing. '
                        'Share only the public key.', size=14, color=SLATE),
                ft.Row([self.generate_button], wrap=True),
                ft.Row([self.public_button, self.private_button], wrap=True, spacing=8),
            ], spacing=12)], visible=False)

        self.form = ft.Column([
            self.operation.control,
            ft.ResponsiveRow([
                ft.Column([caption('Protect with'), self.method.control], spacing=8, col={'xs': 12, 'sm': 6}),
                ft.Column([caption('Input'), self.input_kind.control], spacing=8, col={'xs': 12, 'sm': 6}),
            ], spacing=16, run_spacing=16),
            self.message, self.file_area, self.key_area, self.password, self.confirm,
            self.random_button, self.passphrase_saved, self.key_tools,
            ft.Row([self.run_button, self.clear_button], wrap=True, spacing=8),
        ], spacing=18)
        form_sheet = ft.Container(ft.Column([self.form, self.progress, self.status_bar], spacing=14),
                                  padding=24, bgcolor=PAPER, border_radius=16, border=ft.Border.all(1, HAIRLINE))

        mark = ft.Container(ft.Icon(ft.Icons.LOCK, color=BRASS, size=18), width=36, height=36,
                            border_radius=10, bgcolor=BRASS_TINT, alignment=ft.Alignment.CENTER)
        header = ft.Column([
            ft.Row([ft.Row([mark, ft.Text('Cipher Vault', size=16, weight=ft.FontWeight.W_600, color=INK)],
                           spacing=10, tight=True),
                    ft.Text('Runs on this device. Nothing is uploaded.', size=13, color=SLATE)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True, run_spacing=8),
            ft.Container(height=12),
            ft.Text('Keep your words yours.', size=30, weight=ft.FontWeight.W_600, color=INK),
            ft.Text('Encrypt messages and files with a passphrase or a recipient’s public key.',
                    size=15, color=SLATE),
        ], spacing=6)
        self.view = ft.SafeArea(ft.Container(ft.Column([
            header,
            ft.ResponsiveRow([
                ft.Container(form_sheet, col={'xs': 12, 'lg': 7}),
                ft.Container(ft.Column([
                    self.result_panel,
                    ft.Text('Save results before closing. Forgotten passphrases cannot be recovered. '
                            'Clear the workspace when finished.', size=13, color=SLATE),
                ], spacing=12), col={'xs': 12, 'lg': 5}),
            ], spacing=20, run_spacing=20),
        ], spacing=24, scroll=ft.ScrollMode.AUTO), padding=20, expand=True), expand=True)
        self.curtain = ft.Container(ft.Column([
            ft.Icon(ft.Icons.VISIBILITY_OFF_OUTLINED, color=SLATE, size=28),
            ft.Text('Cipher Vault is hidden while in the background.', size=16, weight=ft.FontWeight.W_600,
                    color=INK, text_align=ft.TextAlign.CENTER),
            ft.Text('Passphrases were cleared. Return to the app to continue.', size=14, color=SLATE,
                    text_align=ft.TextAlign.CENTER),
        ], spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER, expand=True, padding=24, visible=False)

        self.notify('Choose what to do, then add your text or file.')
        self.show_result()

    def notify(self, text, tone='info'):
        icon, color, bgcolor = TONES[tone]
        self.status.value = text
        self.status.color = color
        self.status_icon.icon = icon
        self.status_icon.color = color
        self.status_bar.bgcolor = bgcolor

    def show_result(self):
        kind = self.result_kind if self.result_data is not None else 'empty'
        icon, title, note, sealed, mono = RESULT_STATES[kind]
        text = SEALED_TEXT if sealed else INK
        muted = SEALED_MUTED if sealed else SLATE
        self.result_panel.bgcolor = SEALED if sealed else PAPER
        self.result_panel.border = ft.Border.all(1, SEALED_LINE if sealed else HAIRLINE)
        self.result_icon.icon = icon
        self.result_icon.color = BRASS if sealed else muted
        self.result_title.value = title
        self.result_title.color = text
        self.result_note.value = note
        self.result_note.color = muted
        self.result.text_style = ft.TextStyle(size=13 if mono else 15, color=text,
                                              font_family=self.mono if mono else None)
        self.save_button.style = button_style(SEALED_TEXT, SEALED) if sealed else button_style()

    def changed(self, event=None):
        self.save_button.disabled = self.result_data is None
        hybrid = self.method.value == 'hybrid'
        encrypting = self.operation.value == 'encrypt'
        self.message.visible = self.input_kind.value == 'text'
        self.message.label = 'Message' if encrypting else 'Encrypted text'
        self.message.hint_text = None if encrypting else 'Paste the whole Base64 value'
        self.message.text_style = ft.TextStyle(size=15 if encrypting else 13, color=INK,
                                               font_family=None if encrypting else self.mono)
        self.file_area.visible = not self.message.visible
        self.key_area.visible = hybrid
        self.key_tools.visible = hybrid
        self.verified.visible = hybrid and encrypting
        self.expected_fingerprint.visible = hybrid and encrypting
        self.random_button.visible = encrypting or hybrid
        if self.generated_passphrase is not None and self.password.value != self.generated_passphrase:
            self.generated_passphrase = None
            self.passphrase_saved.value = False
            self.passphrase_saved.visible = False
        self.password.visible = not hybrid or not encrypting or self.key_tools.visible
        self.password.label = 'Private-key passphrase (for decryption / key generation)' if hybrid else 'Passphrase'
        self.confirm.visible = encrypting or hybrid
        self.run_button.content = 'Encrypt' if encrypting else 'Decrypt'
        self.run_button.icon = ft.Icons.LOCK_OUTLINE if encrypting else ft.Icons.LOCK_OPEN_OUTLINED
        self.notify('Inputs changed. The previous result is still available to save.'
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
            content=ft.Text(message), actions=[ft.TextButton('Keep working', style=quiet_style(), on_click=respond(False)),
                                             ft.TextButton('Discard', style=quiet_style(DANGER), on_click=respond(True))],
            on_dismiss=lambda event: finish(False))
        self.page.show_dialog(dialog)
        try:
            return await answer
        finally:
            self.confirming = False

    async def close_window(self, event):
        if event.type in (ft.WindowEventType.MINIMIZE, ft.WindowEventType.HIDE):
            self.set_background(True)
        elif event.type in (ft.WindowEventType.RESTORE, ft.WindowEventType.SHOW, ft.WindowEventType.FOCUS):
            self.set_background(False)
        if event.type != ft.WindowEventType.CLOSE:
            return
        if self.busy:
            self.notify('Wait for the current operation to finish before closing.', 'warning')
            self.page.update()
            return
        if self.unsaved and not await self.confirm_discard('Your unsaved result or generated keys will be lost.'):
            return
        await self.page.window.destroy()

    def forget_passphrases(self):
        self.password.value = self.confirm.value = ''
        self.generated_passphrase = None
        self.passphrase_saved.value = False
        self.passphrase_saved.visible = False

    def set_background(self, hidden):
        self.backgrounded = hidden
        self.view.visible = not hidden
        self.curtain.visible = hidden
        if hidden:
            self.forget_passphrases()
        self.page.update()

    async def lifecycle(self, event):
        if event.state in (ft.AppLifecycleState.HIDE, ft.AppLifecycleState.PAUSE, ft.AppLifecycleState.DETACH):
            self.set_background(True)
        elif event.state in (ft.AppLifecycleState.RESUME, ft.AppLifecycleState.SHOW):
            self.set_background(False)

    async def new_passphrase(self, event=None):
        if self.busy or self.confirming:
            return
        self.generated_passphrase = generate_passphrase()
        self.password.value = self.confirm.value = self.generated_passphrase
        self.passphrase_saved.visible = True
        self.passphrase_saved.value = False
        self.notify('Store this generated passphrase in your password manager before continuing. '
                    'It cannot be recovered.', 'warning')
        self.page.update()

    def check_generated_passphrase(self):
        if (self.generated_passphrase is not None and self.password.value == self.generated_passphrase
                and not self.passphrase_saved.value):
            raise ValueError('Store the generated passphrase securely and confirm before continuing.')

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
            self.notify(str(error), 'error')
        except Exception:
            # Do not surface runtime exception details that could contain user data.
            self.notify('The operation could not finish. Try again or restart the app.', 'error')
        finally:
            self.busy = False
            self.form.disabled = False
            self.progress.visible = False
            self.save_button.disabled = self.result_data is None
            self.show_result()
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
                self.file_label.value = f'{self.file_name}, {len(self.file_data):,} bytes'
                self.file_label.color = INK
                self.changed()
        await self.guarded(work)

    async def pick_key(self, event=None):
        async def work():
            selected = await self.selected_bytes(32768)
            if selected is not None:
                name, data = selected
                self.key_data = None
                self.verified.value = False
                self.expected_fingerprint.value = ''
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
            self.check_generated_passphrase()
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
            self.notify('Encrypting…' if encrypting else 'Decrypting and checking authenticity…')
            self.forget_passphrases()
            self.page.update()
            if hybrid:
                if self.key_data is None:
                    raise ValueError('Choose the recipient public key or your private key first.')
                if encrypting and not self.verified.value:
                    raise ValueError('Verify the public-key fingerprint before encrypting.')
                if encrypting:
                    expected = re.sub(r'[\s:]', '', self.expected_fingerprint.value or '').lower()
                    actual = hybrid_engine.fingerprint(hybrid_engine.public_key(self.key_data))
                    if not re.fullmatch(r'[0-9a-f]{64}', expected) or not hmac.compare_digest(expected, actual):
                        raise ValueError('The trusted recipient fingerprint does not match this public key.')
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
                    self.result_kind = 'sealed'
                    self.result.value = base64.b64encode(output).decode('ascii')
                else:
                    try:
                        self.result.value = output.decode('utf-8')
                        self.result_kind = 'plain'
                    except UnicodeDecodeError:
                        self.result.value = 'Binary result. Save it to a file.'
                        self.result_kind = 'binary'
            else:
                self.result_kind = 'file-encrypted' if encrypting else 'file-decrypted'
                self.result.value = f'{len(output):,} bytes ready to save.'
            self.notify('Complete. Save your result before closing or changing inputs.', 'success')
            self.forget_passphrases()
        await self.guarded(work)

    async def save(self, event=None):
        async def work():
            if self.result_data is not None:
                path = await self.export(self.result_name, self.result_data)
                if path:
                    self.result_saved = True
                    self.notify('Result saved.', 'success')
                else:
                    self.notify('Save cancelled. The result is still available.')
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
            self.check_generated_passphrase()
            if password != self.confirm.value:
                raise ValueError('Confirm the matching private-key passphrase above.')
            self.forget_passphrases()
            self.generated_keys = await asyncio.to_thread(hybrid_engine.generate_keypair, password)
            self.saved_keys.clear()
            self.private_button.disabled = self.public_button.disabled = False
            self.notify('Key pair ready. Save both keys. Share only the public key.', 'warning')
            self.forget_passphrases()
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
                    self.notify(f'Saved {name}.', 'success')
                else:
                    self.notify('Save cancelled. Keys are still available.')
        await self.guarded(work)

    async def clear(self, event=None):
        if self.busy or self.confirming:
            return
        if self.unsaved and not await self.confirm_discard('Clearing will discard unsaved results and generated keys.'):
            return
        self.file_data = self.key_data = self.generated_keys = self.result_data = None
        self.file_name = None
        self.password.value = self.confirm.value = self.message.value = ''
        self.forget_passphrases()
        self.expected_fingerprint.value = ''
        self.file_label.value = 'No file selected.'
        self.file_label.color = SLATE
        self.key_label.value = 'No key selected.'
        self.verified.value = False
        self.public_button.disabled = self.private_button.disabled = True
        self.result.value = ''
        self.result_saved = True
        self.saved_keys.clear()
        self.show_result()
        self.changed()
        self.notify('Workspace cleared.')
        self.page.update()


def main(page: ft.Page):
    if page.web:
        page.add(ft.Text('Cipher Vault requires native local execution. Launch the desktop or mobile app.'))
        return
    page.title = 'Cipher Vault'
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=INK, font_family='Segoe UI', color_scheme=ft.ColorScheme(
        primary=INK, on_primary=PAPER, surface=PAPER, on_surface=INK, on_surface_variant=SLATE,
        outline=LINE, outline_variant=HAIRLINE, error=DANGER))
    page.bgcolor = STEEL
    page.padding = 0
    page.window.width = 1120
    page.window.height = 880
    app = VaultApp(page)
    page.on_app_lifecycle_state_change = app.lifecycle
    if app.desktop:
        page.window.prevent_close = True
        page.window.on_event = app.close_window
    page.add(app.view, app.curtain)
