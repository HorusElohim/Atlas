---
name: app-signing-and-distribution
description: "CI-sign and distribute Android/iOS/macOS release builds."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [android, ios, macos, signing, testflight, notarization, ci, distribution, keystore, apple-developer]
    related_skills: [flutter-rust-bridge, xcode-build-graph-repair, github]
---

# App signing and distribution

For taking a Flutter/native app from "builds in CI" to "a tester can install
it." Each platform needs its own signing identity and its own CI wiring; this
skill covers all three plus the meta-pattern of designing the CI action so it
degrades gracefully when secrets are absent (PRs/forks keep building).

## The shape of the problem

A CI pipeline that *builds* an app is not the same as one that *distributes*
it. Builds succeed with no signing identity at all (`--no-codesign` on iOS,
debug-signed APK on Android, unsigned `.app` on macOS) — that's often what's
already in place and looks done, but none of those artifacts run on anyone's
real device without an install-key bypass. Before promising "just needs a
few secrets," audit what the existing CI actions actually produce: read
every `.github/actions/build-*/action.yml`, note which ones pass `--no-codesign`
or produce debug-signed output, and say so explicitly — the gap between
"CI is green" and "a tester can install this" is exactly the missing signing
step, and it is invisible from a passing pipeline run alone.

## Android: keystore stability is the whole game

Generate once, keep forever:

```bash
keytool -genkeypair -v \
  -keystore release.jks -alias <app> \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass '<random-32-char>' -keypass '<same>' \
  -dname "CN=<App>, OU=<App>, O=<App>, L=Unknown, ST=Unknown, C=US"

base64 -w0 release.jks | gh secret set ANDROID_RELEASE_KEYSTORE_BASE64
gh secret set ANDROID_RELEASE_KEYSTORE_PASSWORD -b '<password>'
```

**Losing this file is not recoverable and is not merely inconvenient.** A
new keystore means a new signing identity, which means Android treats it as
a *different app* — every existing install can no longer be updated in
place; users must uninstall (losing local data) and reinstall fresh. State
this consequence explicitly and tell the user to back the file up (password
manager, encrypted archive) the moment it's generated — do not just generate
it and move on silently. Leave the local copy in place after setting the
GitHub secret; do not delete it as "cleanup," since the secret store is
write-only (you can set it, you can never read it back to re-derive a local
backup).

## Verify Android signing inputs before configuring anything

Before creating `android/key.properties`, setting CI secrets, or building a
release artifact, verify all three inputs against the actual keystore file:

1. the keystore loads with the supplied **store password**;
2. the requested alias exists;
3. the exported certificate SHA-256 matches the expected upload certificate.

Use a non-printing password variable and report only the alias, verification
status, and certificate fingerprint. A password that unlocks the private key
may differ from the store password, so do not assume one value works for both
unless keytool verifies it. If verification fails, do not create local signing
files and do not overwrite write-only GitHub secrets with an unverified value.
Keep the keystore and `key.properties` ignored, and verify the final APK with
`apksigner --print-certs` after building. The concise repeatable checklist is in
`references/android-signing-verification.md`.

### Android CI preflight and path integrity

When CI reports the expected certificate but the actual APK digest is missing,
the keystore secret is probably valid while Gradle did not load
`key.properties` and produced an unsigned/debug-signed release artifact. Make
the CI action fail closed before Gradle: decode the keystore, validate its
alias/password with `keytool -list`, assert the decoded file and properties file
are non-empty, and write an absolute `storeFile` path. Then verify the final
APK with the same `keytool`-derived certificate digest and `apksigner
verify --print-certs`; never infer signing from a successful build alone. The
reusable sequence is in `references/android-ci-signing-preflight.md`.

If an upload key is lost and the owner authorizes rotation, preserve the old
file as a dated backup, generate the replacement once with a documented alias,
update both the base64 and password repository secrets, and record the new
certificate fingerprint. Explicitly warn that existing installations signed by
the old key cannot be updated in place and require one uninstall/reinstall.
Never print or commit passwords, keystores, or `key.properties`.

### CI signer-parser hardening

When `keytool` computes the expected digest but CI reports an empty or textual
actual digest, capture the complete `apksigner verify --print-certs` output from
both stdout and stderr. Extract only a strict 64-hex SHA-256 token (optionally
colon-separated); reject labels such as `CERTIFICATESHA-256DIGEST`. If no
strict token is found, print the non-secret verifier diagnostics and fail. A
successful Gradle build is not proof that the APK is signed. The reusable
procedure is in `references/android-ci-signing-preflight.md`.

## iOS: App Store Connect API key drives everything, no manual cert export

Three things needed, only obtainable by someone with access to the Apple
Developer account (this is Apple-account administrative work an agent cannot
do on the user's behalf — say so plainly and hand back a numbered checklist
rather than attempting a workaround):

1. Active Apple Developer Program enrollment for the team ID already in the
   Xcode project (`grep DEVELOPMENT_TEAM ios/Runner.xcodeproj/project.pbxproj`).
2. An App Store Connect app record for the bundle ID.
3. An App Store Connect API key (Users and Access → Integrations → App
   Manager role) — download the `.p8` once (only downloadable once), note
   its Key ID and Issuer ID.

```bash
base64 -w0 AuthKey_XXXXXXXXXX.p8 | gh secret set ASC_API_KEY_BASE64
gh secret set ASC_API_KEY_ID -b 'XXXXXXXXXX'
gh secret set ASC_API_ISSUER_ID -b '<issuer-uuid>'
```

**Critical implementation detail:** `flutter build ipa --export-options-plist=...`
cannot forward `-allowProvisioningUpdates`/`-authenticationKeyPath`/
`-authenticationKeyID`/`-authenticationKeyIssuerID` into its own internal
`xcodebuild archive` invocation — there is no passthrough flag for it. Call
`xcodebuild archive` and `xcodebuild -exportArchive` **directly** instead:

```bash
# Compile Dart/assemble frameworks without codesign (same as flutter's own
# unsigned path) — xcodebuild below does the real, authenticated signing.
flutter build ios --release --no-codesign

auth_args=(
  -allowProvisioningUpdates
  -authenticationKeyPath "$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8"
  -authenticationKeyID "$KEY_ID"
  -authenticationKeyIssuerID "$ISSUER_ID"
)
xcodebuild archive -workspace ios/Runner.xcworkspace -scheme Runner \
  -configuration Release -archivePath build/ios/archive/Runner.xcarchive \
  -destination 'generic/platform=iOS' "${auth_args[@]}"
xcodebuild -exportArchive -archivePath build/ios/archive/Runner.xcarchive \
  -exportPath build/ios/ipa -exportOptionsPlist ios/ExportOptions.plist \
  "${auth_args[@]}"
```

The `.p8` key must live at `~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8`
(the fixed path `xcodebuild` reads itself). With `-allowProvisioningUpdates`
and a valid key, Xcode creates/downloads the distribution certificate and
provisioning profile itself, headless — no manual `.p12`/`.mobileprovision`
export needed for this platform. Set `ExportOptions.plist`'s
`<key>destination</key><string>upload</string>` with `method` = `app-store-connect`
so the export step uploads to TestFlight directly; keep an explicit
`xcrun altool --upload-app` fallback step as a documented retry path since
that auto-upload has known silent-noop quirks on some Xcode versions.

## macOS: separate cert type, same API key for notarization

Developer ID Application certificate (NOT the Apple Distribution cert used
for iOS/TestFlight — different cert type, same Apple Developer Program
membership). Export as `.p12` from Keychain Access, then:

```bash
base64 -w0 DeveloperID.p12 | gh secret set MACOS_DEVELOPER_ID_CERT_BASE64
gh secret set MACOS_DEVELOPER_ID_CERT_PASSWORD -b '<export password>'
```

Import into a **job-scoped temporary keychain** in CI — created and
destroyed entirely within the same job, never touching the runner's login
keychain:

```bash
keychain="signing.keychain-db"; kc_pw="$(openssl rand -base64 24)"
security create-keychain -p "$kc_pw" "$keychain"
security set-keychain-settings -lut 21600 "$keychain"
security unlock-keychain -p "$kc_pw" "$keychain"
security import cert.p12 -k "$keychain" -P "$CERT_PASSWORD" \
  -T /usr/bin/codesign -T /usr/bin/security
security set-key-partition-list -S apple-tool:,apple: -s -k "$kc_pw" "$keychain"
security list-keychains -d user -s "$keychain" $(security list-keychains -d user | tr -d '"')
# ... codesign --deep --options runtime --sign "$identity" --keychain "$keychain" App.app
security delete-keychain "$keychain"   # in an always-run cleanup step
```

Then notarize with the **same** `ASC_API_KEY_*` secrets from the iOS setup
(one API key, both platforms — don't provision a second one):

```bash
ditto -c -k --keepParent App.app app.zip
xcrun notarytool submit app.zip --key "$KEY_PATH" --key-id "$KEY_ID" \
  --issuer "$ISSUER_ID" --wait
xcrun stapler staple App.app
```

Without notarization the app is still usable (signed alone silences most
Gatekeeper friction to a one-time right-click-Open bypass) — treat
signing-only as a legitimate intermediate state, not a failure, when the API
key isn't set up yet.

### Critical: never upload the raw .app directory as the CI artifact

A `.app` bundle is a directory tree full of symlinks — every framework under
`Contents/Frameworks` carries a `Versions/Current -> A` symlink, and some
(mpv.framework is a confirmed real-world case) additionally have a
top-level binary symlink into that versioned directory. Handing the raw
`.app` directory straight to `actions/upload-artifact` lets its own
archiver zip it — and that archiver does not reliably preserve symlinks for
a directory input. On download, a symlink can come back as an independent
second copy of the real file it pointed at.

**Symptom, exactly as reported by a tester:**
```
objc[92082]: Class Mpv is implemented in both .../Mpv.framework/Versions/A/Mpv
  and .../Mpv.framework/Mpv. This may cause spurious casting failures...
[... repeated per class ...]
Assertion failed: (group_index >= 0), function m_config_cache_from_shadow
💣 Program crashed: Signal 6
```
dyld loads the framework's binary twice, under two different paths, and
registers every Objective-C class in it twice — the "implemented in both"
warnings are the direct symptom, and the subsequent crash is exactly this
undefined behavior surfacing in whichever library first hits corrupted
shared state (mpv's internal config cache in the case above, but any
framework in the bundle is equally at risk).

**Fix — zip it yourself with `ditto` before uploading, upload the zip, not
the directory:**
```bash
# ditto is the tool Xcode itself uses to package a .app for notarization/
# export, and it correctly preserves symlinks, resource forks, and code
# signatures — unlike a generic zip of the directory tree.
ditto -c -k --keepParent build/macos/Build/Products/Release/App.app portalis-macos.zip
```
Then point `actions/upload-artifact`'s `path:` at that single zip file, not
the `.app` directory. This applies whether or not the app is
signed/notarized — do it unconditionally, as its own step after signing.

**Consequence to document for testers:** GitHub always wraps whatever you
upload in its own outer zip, so the artifact a tester downloads from the
Actions UI is now a zip-of-a-zip — double-click once to get
`portalis-macos.zip`, double-click *that* to get the real `.app`. State this
explicitly in the distribution doc, and give the tell-tale sign that
someone stopped after only the first extraction: they end up running the
app via a bare path like `.../Downloads/Contents/MacOS/portalis` instead of
double-clicking a `.app` bundle — if you see that path shape reported, the
fix above didn't run, or they only extracted once.

## CI action design: degrade gracefully, don't hard-fail on missing secrets

Every build-* action in this pattern should check `if secret != ''` and fall
back to its previous (unsigned) behavior when a signing secret is absent,
with an `::notice::`/`::warning::` explaining what's missing and pointing at
the setup doc — rather than failing the whole job. This keeps PRs from forks
(which can't see repo secrets) building green, and keeps the platform
matrix bisectable: you can land the CI logic and the docs before the account
administrative work is even done, and each platform unlocks independently
the moment its secrets land.

## Write a DISTRIBUTION.md, not just working CI

After wiring the CI side, write a single doc that separates "done, nothing
left to do" from "blocked on account work only the user can do" per
platform, with the exact `gh secret set` commands to run once each
credential is obtained. This is the deliverable a non-technical stakeholder
reads to know what's actually left — a green CI run alone does not answer
that question.

## Verifying without a macOS/iOS host

When developing this on Linux (no Xcode available to execute the iOS/macOS
steps locally): validate YAML syntax (`python3 -c "import yaml; yaml.safe_load(open(f))"`
for every touched action/workflow file) and cross-check every flag against
current documentation/community examples before committing — don't guess at
`xcodebuild`/`notarytool` flag names from memory, they've changed across
Xcode versions and a wrong flag only surfaces on the next real macOS CI run,
which is expensive to iterate on. Say plainly in the commit message and to
the user that the platform-specific logic could not be exercised locally and
needs a real run to confirm end-to-end.
