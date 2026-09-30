# Cipher Vault

A Flet desktop/mobile encryption app with a Python `cryptography` engine. The old letter-shifting cipher and Tkinter interface have been removed.

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
3. Enter and confirm a strong passphrase of at least 12 characters.
4. Click **Encrypt**, then **Save result**.
5. To decrypt, select **Decrypt**, provide the encrypted text or file, and enter the same passphrase.

Encrypted text in the result box is Base64: copy the whole value when pasting it back into text mode. Saved results use the binary `.cvlt` format and should be reopened in **File** mode. Text results can be selected and copied using the platform's standard controls.

A `.cvlt` file includes a version, a random 16-byte salt, a fixed PBKDF2 work factor, and a Fernet token. PBKDF2-HMAC-SHA256 uses 1,200,000 iterations to derive a 32-byte Fernet key. Fernet uses AES-128-CBC plus HMAC-SHA256; it is **not AES-256**. An authenticated copy of the header is inside the token. Unsupported parameters are rejected before running the KDF, and decryption completes authentication before exposing any output.

The salt is not secret and does not need to be stored separately. A fresh salt is generated each time. Fernet tokens reveal their creation time. A strong passphrase matters; this application cannot recover a forgotten password.

## Public-key encryption

Choose **Public key (AES + RSA)** for the existing hybrid format. It uses AES-256-GCM for data and RSA-OAEP-SHA256 to wrap a fresh AES key per encryption. Existing `.cse` files retain their original format and cryptographic context; the old format identifier is preserved only for compatibility.

To generate keys, enter and confirm a private-key passphrase, expand **Create a public/private key pair**, generate, and save **both** PEM files. Generation creates RSA-3072 keys and encrypts the private key at rest. Save them before clearing or closing the app. Public/private keys generated here remain compatible with the previous hybrid implementation.

For encryption, choose the recipient's public PEM key and verify the displayed SHA-256 fingerprint over a trusted channel before selecting the confirmation checkbox. For decryption, choose your private PEM key and provide its passphrase. Share only the public key. Hybrid encryption does not authenticate the sender and provides no forward secrecy or replay protection.

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

**Build status:** source code and automated tests are provided. No Windows installer, APK, macOS app, or IPA has been built or device-tested in this migration. Flet packaging must resolve compatible native `cryptography` wheels for each target Python version and architecture; desktop pip installation alone does not verify this. Test file import/export, application lifecycle, memory use, and encryption on real devices before distribution.

The UI uses responsive rows, scrolling, safe-area padding, masked passphrase fields, and background cryptographic tasks. Native file pickers read and save bytes, so Android/iOS do not need desktop filesystem paths. The picker may load a whole file before the application can enforce its limit. This project targets native local execution; do not host it as a remote web service without redesigning its privacy and transport assumptions.

## Limits and security scope

- New plaintext files are limited to 16 MiB for mobile memory use; selected encrypted files are limited to 24 MiB. Older hybrid files beyond that UI limit can still be read through the hybrid Python engine, whose original limits remain intact.
- Text mode accepts up to 250,000 plaintext characters. Use file mode for larger messages.
- Whole files and results are held in memory; this is not streaming encryption.
- Native save dialogs handle destinations and overwrite confirmation. Choose a new output filename to preserve your originals.
- **Clear workspace** removes the application's references to passwords, messages, files, and generated keys. It is destructive; save your work first. Python and the UI runtime do not guarantee memory zeroization.
- Data is not persisted automatically. Closing the app or the mobile OS terminating it loses unsaved results and generated keys. Do not close during an operation.
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
