# Release candidate 0.3.1

Status: **not approved for production distribution**.

## Verified locally

- 42 automated tests passed on Windows/Python 3.14.7 after password/fingerprint/privacy hardening. The previous 25-test suite also passed on Python 3.10.9.
- Whole-environment dependency audit after upgrading pip/setuptools: no known vulnerabilities reported.
- Desktop file export writes and flushes a same-directory temporary file, then publishes it atomically without overwriting an existing target. Unsupported filesystems fail closed.
- Input edits preserve the previous result; replacing or clearing unsaved output asks for confirmation.
- Desktop close is blocked during an operation and prompts for unsaved results/keys.
- Generated keys remain marked unsaved until both exports succeed.
- Remote web execution is refused before any secret-entry controls are created.
- Release code and build configuration pin `cryptography==50.0.1` and Flet 1.0.3.
- Hardened Windows 0.3.1 executable built with PyInstaller 6.22.3 at `dist/windows-0.3.1/CipherVault.exe`. It is an **unsigned candidate**, not a production-approved release. The previous executable is preserved separately.
- On 2026-10-01, built `dist/installers/CipherVault-Setup-0.3.1-x64.exe` using Inno Setup 6.7.3. Silent per-user installation into an isolated project folder passed; the installed payload hash matched and its cryptographic self-test passed. Uninstallation removed the executable and uninstall registration while preserving a synthetic user-data file. Reports and SHA-256 are in `dist/installers`. Start menu/optional desktop shortcuts are configured, but visual wizard/shortcut interaction and clean-machine UI testing remain unverified. The installer is unsigned.
- The executable's own offline self-test passed: password binary round trip, wrong-password rejection, and RSA/AES binary round trip. Bundled versions: Python 3.14.7, cryptography 50.0.1, Flet 1.0.3, OpenSSL 4.0.2.
- The separate release environment audit reported no known vulnerabilities. `dist/windows-0.3.1` contains `runtime-check.json`, the existing unchanged-environment `dependency-audit.json`, `manifest.json`, and `SHA256.txt` alongside the rebuilt executable. Its bundled self-test passed again after hardening.

## Release blockers

1. **Mobile native dependency availability.** On 2026-09-30 the public Flet index offered cryptography 48.0.0 for Python 3.14 mobile targets. Audit reported advisories including PYSEC-2026-3552, PYSEC-2026-3553, PYSEC-2026-3554 and GHSA-537c-gmf6-5ccf. An Android arm64 wheel-resolution check against PyPI and the Flet index found no cryptography 50.0.1 wheel. Obtain or reproducibly build and audit compatible patched wheels for Android and iOS; do not downgrade the pin. Repeat the check when the indexes change.
2. **Native release builds and UI tests.** The Flutter Windows build packaged Python successfully but failed because the Visual Studio C++ toolchain was missing. The supported PyInstaller route produced the candidate described above. Its cryptographic runtime was verified, but the Windows UI automation service was unavailable, so visual/native interaction verification was not completed. macOS and iOS require macOS runners; no Apple artifacts have been built here.
3. **Device behavior.** Test Android/iOS import/export with actual document providers, empty files, interrupted saves, cancellation, backgrounding, process termination, and low-memory conditions. The mobile picker reads bytes before size validation and controls the durability of native saves. The empty-file adapter uses a narrowly scoped Flet 1.0.3 service compatibility call and needs native validation.
4. **Distribution identity and signing.** Choose a permanent application ID owned by the publisher. Supply Windows code signing, Android release signing, and Apple signing/notarization credentials through secure build infrastructure. Never commit these credentials. The candidate workflow does not publish or produce signed store releases; its iOS target is the simulator only.
5. **Independent security assessment.** Audit the custom formats, platform file access, memory handling, dependency/native-library inventory, and release process before using a production security claim.

## Security test results — 2026-09-30

### Additional hardening in 0.3.1

- New passphrases require 15 characters and reject obvious repeated/predictable choices. An offline 192-bit random generator requires confirmation that its output has been stored before use. This is not a full compromised-password corpus.
- Public-key encryption checks the entire externally supplied fingerprint against the selected key each time, in addition to the user's confirmation checkbox.
- Passphrase fields are cleared before cryptographic work; background/minimize events clear passphrases and hide the workspace. This is a privacy curtain rather than an authenticated lock, and does not remove unsaved plaintext from process memory or guarantee OS snapshot protection.
- Regression tests verify legacy password/key compatibility, generated-password confirmation, fingerprint mismatch rejection, field clearing, and background events during encryption. All 42 tests pass.
- Existing formats are unchanged. Previously weak passwords are not strengthened automatically; decrypt and re-encrypt those files with a new strong passphrase.

### Previous 0.3.0 test run

`test_security.py` adds nine adversarial tests. The full 34-test suite passed with no failures. Coverage includes 200 deterministic random malformed inputs against both parsers (rejected before key derivation/private-key loading), truncated password envelopes, modified Fernet version/timestamp/IV/ciphertext/HMAC, modified AES-GCM nonce/ciphertext/tag and RSA-wrapped key, JSON type confusion/extra fields, weak RSA and non-RSA public keys, an actual 16 MiB plaintext round trip and limit rejection, simultaneous exports to the same target, and unsupported-filesystem failures. Existing tests cover wrong passwords/keys, encrypted private-key serialization, disk flush errors, and prevention of unauthenticated plaintext output in the tested workflows.

The refreshed audit of `.venv-release/Lib/site-packages` reported no known vulnerabilities; the machine-readable result is `dependency-audit.json`. No application implementation changes were required by these tests, so the existing executable remains unchanged.

These are bounded automated checks using synthetic data, not an exhaustive fuzzer or independent penetration test. They do not validate native mobile document providers, memory zeroization, side channels, compromised endpoints, native-library supply chains, signing, or real-device lifecycle behavior. The mobile-wheel and other release blockers above remain open.

## Build checks

`.github/workflows/verify.yml` runs tests across Windows/macOS/Linux and two Python versions, plus dependency auditing. `.github/workflows/build-candidates.yml` is manual-only and prepares Windows (PyInstaller), Android, macOS, and iOS-simulator candidates. It also runs the Windows executable's self-test. These workflow files have not run on a hosted runner yet. Mobile jobs should fail while patched native wheels are unavailable.

`scripts/build_windows.ps1` reproduces the Windows package from `.venv-release`, then runs its offline self-test and calculates a hash. The release environment must contain Python 3.14, `requirements.txt`, and PyInstaller 6.22.3. The script replaces only generated packaging work/output directories under this project.

Before distribution, archive platform dependency inventories, native OpenSSL versions, audit results, artifact SHA-256 hashes, test-device/OS versions, and signing verification. Verify an encrypted file produced on each platform decrypts on every other platform. Test wrong passwords, malformed envelopes, truncation, changed salts/tags, maximum-size input, export cancellation, and full-disk behavior.

## Residual limits

The app is offline and has no recovery service. It does not guarantee memory erasure, conceal filenames/sizes/timestamps, verify senders, or recover lost passwords/private keys. Mobile operating systems may terminate the app without a close prompt. A process crash can leave a hidden `.cipher-vault-*.tmp` file in the selected desktop output directory; the destination remains unpublished unless the complete write succeeded. Clear leftover temporary files only after checking there is no active export.
