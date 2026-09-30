"""Compatibility adapter for the pinned Flet 1.0.3 mobile save API."""

import flet as ft


async def save_mobile_bytes(picker, name, data):
    if data:
        return await picker.save_file(file_name=name, src_bytes=data)
    # Flet 1.0.3 rejects b'' as if it were None. The native method accepts an
    # explicit empty byte array; preserve that distinction at the service call.
    # Keep this narrowly scoped and revalidate when updating the Flet pin.
    return await picker._invoke_method('save_file', {
        'dialog_title': None, 'file_name': name, 'initial_directory': None,
        'file_type': ft.FilePickerFileType.ANY, 'allowed_extensions': None,
        'src_bytes': b'',
    }, timeout=3600)
