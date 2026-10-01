# Cipher Vault

A Flet desktop/mobile encryption app with a Python `cryptography` engine. The old letter-shifting cipher and Tkinter interface have been removed.

**Release candidate 0.3.1:** hardening is in progress; see [release status and blockers](RELEASE_STATUS.md) before distribution. This is not yet approved for production use across all four platforms.

The Windows installer is **`dist/installers/CipherVault-Setup-0.3.1-x64.exe`**. Send this single file to friends with 64-bit Windows 10/11. They can run it and open Cipher Vault from the Start menu; no separate Python installation is needed. Setup installs for the current user, offers an optional desktop shortcut, and supports removal through Windows Settings > Apps. Store encrypted files and keys outside the installation folder. Flet may download its desktop client on first launch.

This is an unsigned test release, so Windows may show an unknown-publisher warning. Do not disable security protections. Installation, the installed executable's cryptographic self-test, and uninstallation were checked locally; full native interface testing is still outstanding. `dist/installers` contains the installer SHA-256 and test reports. The hardened portable executable remains at `dist/windows-0.3.1/CipherVault.exe`.

To rebuild the installer after building the executable, use `scripts/build_installer.ps1` with Inno Setup 6 installed (pass `-Compiler` with the path to `ISCC.exe`). Alternatively, invoke `ISCC.exe installer/CipherVault.iss` directly. The installer source is in `installer/`.

## Run on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Python 3.10+ is required for source development. The original `Encrpyt Decrypt Software.py` filename also launches the new app. Flet may download its desktop client on first launch. Encryption itself requires no network connection.

## Password encryption

1. Choose **Password**, then **Encrypt**.
2. Type text or choose **File** and select a local file.
3. Enter and confirm a unique passphrase of at least 15 characters, or use **Generate strong passphrase**. Store a generated passphrase securely and confirm that you have done so before proceeding.
4. Click **Encrypt**, then **Save result**.
5. To decrypt, select **Decrypt**, provide the encrypted text or file, and enter the same passphrase.

Encrypted text in the result box is Base64: copy the whole value when pasting it back into text mode. Saved results use the binary `.cvlt` format and should be reopened in **File** mode. Text results can be selected and copied using the platform's standard controls.

A `.cvlt` file includes a version, a random 16-byte salt, a fixed PBKDF2 work factor, and a Fernet token. PBKDF2-HMAC-SHA256 uses 1,200,000 iterations to derive a 32-byte Fernet key. Fernet uses AES-128-CBC plus HMAC-SHA256; it is **not AES-256**. An authenticated copy of the header is inside the token. Unsupported parameters are rejected before running the KDF, and decryption completes authentication before exposing any output.

The salt is not secret and does not need to be stored separately. A fresh salt is generated each time. Fernet tokens reveal their creation time. A strong passphrase matters; this application cannot recover a forgotten password.

New passwords and private-key passphrases are checked locally for minimum length, obvious repetition, and a small list of predictable examples. This is not a comprehensive breach-password database or a guarantee of strength. The generator uses 24 cryptographically random bytes (192 bits), encoded as 32 URL-safe characters; it does not copy anything to the clipboard. Existing files and keys continue to accept their original passwords, including passwords that do not meet the new creation rules.

## Public-key encryption

Choose **Public key** for the existing hybrid format. It uses AES-256-GCM for data and RSA-OAEP-SHA256 to wrap a fresh AES key per encryption. Existing `.cse` files retain their original format and cryptographic context; the old format identifier is preserved only for compatibility.

To generate keys, enter and confirm a private-key passphrase, expand **Create a public/private key pair**, generate, and save **both** PEM files. Generation creates RSA-3072 keys and encrypts the private key at rest. Save them before clearing or closing the app. Public/private keys generated here remain compatible with the previous hybrid implementation.

For encryption, choose the recipient's public PEM key and obtain its SHA-256 fingerprint from the recipient over a separate trusted channel. Paste the full fingerprint into the input and confirm verification. Encryption checks that the fingerprint matches the actual selected key each time; a checkbox alone is insufficient. Copying the displayed fingerprint from an untrusted key defeats this check. For decryption, choose your private PEM key and provide its passphrase. Share only the public key. Hybrid encryption does not authenticate the sender and provides no forward secrecy or replay protection.

## Desktop and mobile builds

`pyproject.toml` defines a Flet project with `src/main.py` as its entry point. Only `src` is packaged; local keys, virtual environments, and tests at the repository root are excluded by construction. Do not put user data or keys inside `src`.

Use Flet's packaging tools for this Flet app; Briefcase and Buildozer are not its packaging route.

```powershell
# From Windows, with the platform build toolchains available:
.\.venv\Scripts\flet.exe build windows
.\.venv\Scripts\flet.exe build apk
```

On macOS, in an environment containing these dependencies:

```sh
flet build macos
flet build ipa
```

Windows builds require the Windows/Flutter build prerequisites. Android requires the Android SDK/JDK and release signing for distribution. macOS/iOS builds require macOS and the Apple toolchain; iOS distribution also requires signing. See [Flet publishing](https://flet.dev/docs/publish/), [Android packaging](https://flet.dev/docs/publish/android/), and [iOS packaging](https://flet.dev/docs/publish/ios/).

**Build status:** see [RELEASE_STATUS.md](RELEASE_STATUS.md) for current evidence. Every platform pins `cryptography==50.0.1`. The older 48.0.0 mobile wheels available from the Flet index failed vulnerability auditing; Android/iOS builds need compatible patched native wheels before release. Desktop pip installation alone does not verify mobile compatibility.

The UI uses responsive rows, scrolling, safe-area padding, masked passphrase fields, and background cryptographic tasks. Desktop reads are bounded before loading a file. Android/iOS pickers use bytes without desktop paths, but may load a whole file before the application can enforce its limit. The app refuses web mode to keep secrets out of a remote Python server.

## Limits and security scope

- New plaintext files are limited to 16 MiB for mobile memory use; selected encrypted files are limited to 24 MiB. Older hybrid files beyond that UI limit can still be read through the hybrid Python engine, whose original limits remain intact.
- Text mode accepts up to 250,000 plaintext characters. Use file mode for larger messages.
- Whole files and results are held in memory; this is not streaming encryption.
- Desktop exports flush to a temporary file and atomically publish to a new filename. Existing files are never replaced; destinations without hard-link support are rejected. Mobile save durability and overwrite behavior are controlled by the native document provider.
- Input changes retain the previous result. Replacing an unsaved result or clearing unsaved output/keys requires confirmation. **Clear workspace** removes application references, but Python and the UI runtime do not guarantee memory zeroization.
- Desktop close prompts protect unsaved results/keys and prevent closing during an operation. Mobile process termination can still lose unsaved data; save results and keys promptly.
- Passphrase fields are cleared before encryption/decryption/key-generation work and on background/minimize events. The workspace is hidden while backgrounded and restored on return; this is a privacy curtain, not an authenticated vault lock. Unsaved output and encrypted key exports stay in memory. Platform snapshots, malware, clipboard copies, runtime copies of passwords, and memory erasure are not controlled by this feature; real-device lifecycle testing remains required.
- Authentication detects modifications; it cannot prevent deletion or replacement with another valid encrypted file. File names, approximate sizes, and Fernet timestamps are not hidden.
- This is an application prototype using established cryptographic primitives, not an independently audited production security product.

References: [Fernet and password key derivation](https://cryptography.io/en/latest/fernet/), [AES-GCM](https://cryptography.io/en/latest/hazmat/primitives/aead/), and [RSA-OAEP](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/).

## Tests and source layout

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

- `src/cipher_vault/app.py`: responsive Flet controls and asynchronous workflows.
- `src/cipher_vault/password_crypto.py`: password envelope and validation.
- `src/cipher_vault/hybrid_crypto.py`: compatible AES/RSA engine.
- `test_password_crypto.py`: round trips, salts, tampering, malformed data, and input limits.
- `test_hybrid_crypto.py`: hybrid authentication and key validation.
- `test_app.py`: Flet control construction and event-handler tests with mocked native dialogs; these are not end-to-end device tests.
- `test_storage.py`: interrupted desktop exports, non-overwrite guarantees, and bounded reads.
- `.github/workflows/verify.yml`: cross-platform tests and dependency audits.
- `.github/workflows/build-candidates.yml`: manual unsigned candidate builds, including the iOS simulator.
