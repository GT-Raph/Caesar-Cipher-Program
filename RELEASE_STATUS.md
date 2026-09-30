# Release candidate 0.3.0

Status: **not approved for production distribution**.

## Verified locally

- 25 automated tests passed on Windows/Python 3.10.9.
- Whole-environment dependency audit after upgrading pip/setuptools: no known vulnerabilities reported.
- Desktop file export writes and flushes a same-directory temporary file, then publishes it atomically without overwriting an existing target. Unsupported filesystems fail closed.
- Input edits preserve the previous result; replacing or clearing unsaved output asks for confirmation.
- Desktop close is blocked during an operation and prompts for unsaved results/keys.
- Generated keys remain marked unsaved until both exports succeed.
- Remote web execution is refused before any secret-entry controls are created.
- Release code and build configuration pin `cryptography==50.0.1` and Flet 1.0.3.

## Release blockers

1. **Mobile native dependency availability.** On 2026-09-30 the public Flet index offered cryptography 48.0.0 for Python 3.14 mobile targets. Audit reported advisories including PYSEC-2026-3552, PYSEC-2026-3553, PYSEC-2026-3554 and GHSA-537c-gmf6-5ccf. An Android arm64 wheel-resolution check against PyPI and the Flet index found no cryptography 50.0.1 wheel. Obtain or reproducibly build and audit compatible patched wheels for Android and iOS; do not downgrade the pin. Repeat the check when the indexes change.
2. **Native release builds and runtime tests.** No completed release artifacts are verified yet. The Windows build attempted to install Flutter 3.44.8. macOS and iOS require macOS runners. The Windows UI automation service was unavailable, so visual/native interaction verification was not completed.
3. **Device behavior.** Test Android/iOS import/export with actual document providers, empty files, interrupted saves, cancellation, backgrounding, process termination, and low-memory conditions. The mobile picker reads bytes before size validation and controls the durability of native saves. The empty-file adapter uses a narrowly scoped Flet 1.0.3 service compatibility call and needs native validation.
4. **Distribution identity and signing.** Choose a permanent application ID owned by the publisher. Supply Windows code signing, Android release signing, and Apple signing/notarization credentials through secure build infrastructure. Never commit these credentials. The candidate workflow does not publish or produce signed store releases; its iOS target is the simulator only.
5. **Independent security assessment.** Audit the custom formats, platform file access, memory handling, dependency/native-library inventory, and release process before using a production security claim.

## Build checks

`.github/workflows/verify.yml` runs tests across Windows/macOS/Linux and two Python versions, plus dependency auditing. `.github/workflows/build-candidates.yml` is manual-only and prepares Windows, Android, macOS, and iOS-simulator candidates. These workflow files have not run on a hosted runner yet. Mobile jobs should fail while patched native wheels are unavailable.

Before distribution, archive platform dependency inventories, native OpenSSL versions, audit results, artifact SHA-256 hashes, test-device/OS versions, and signing verification. Verify an encrypted file produced on each platform decrypts on every other platform. Test wrong passwords, malformed envelopes, truncation, changed salts/tags, maximum-size input, export cancellation, and full-disk behavior.

## Residual limits

The app is offline and has no recovery service. It does not guarantee memory erasure, conceal filenames/sizes/timestamps, verify senders, or recover lost passwords/private keys. Mobile operating systems may terminate the app without a close prompt. A process crash can leave a hidden `.cipher-vault-*.tmp` file in the selected desktop output directory; the destination remains unpublished unless the complete write succeeded. Clear leftover temporary files only after checking there is no active export.
