"""Local checks for newly created secrets; never restrict legacy decryption."""

import re
import secrets


def validate_new(password, max_bytes=1024):
    if len(password) < 15 or len(password.encode('utf-8')) > max_bytes:
        raise ValueError(f'Use at least 15 characters and at most {max_bytes} UTF-8 bytes.')
    folded = re.sub(r'[^a-z0-9]', '', password.casefold())
    if not password.strip() or len(set(password)) < 5:
        raise ValueError('Choose a less predictable passphrase or generate a random one.')
    if re.fullmatch(r'(.{1,8})\1+', password, flags=re.DOTALL):
        raise ValueError('Repeated patterns are easy to guess. Use a unique passphrase.')
    # Small offline blocklist: explicitly not a comprehensive breach database.
    if folded in {'password123456789', '123456789012345', '12345678901234567890',
                  'qwertyuiopasdfgh', 'letmeinletmeinletmein', 'correcthorsebatterystaple'}:
        raise ValueError('This is a commonly used example or predictable password. Choose another.')


def generate():
    return secrets.token_urlsafe(24)  # 192 random bits, no clipboard/network use.
