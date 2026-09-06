---
name: android-release-signing
description: "Use when rotating Android signing keys. Verify CI and APKs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [android, signing, keystore, ci, apk, release]
---

# Android release signing

Use this class skill when an Android release APK must be signed consistently,
when a keystore is missing or lost, or when CI reports an APK certificate
mismatch. The deliverable is a verified signed artifact, not merely a Gradle
build that exits successfully.

## Safety and identity rules

- A keystore is an application identity. Losing it is not recoverable through
  Android or GitHub; a replacement key prevents existing installations signed
  by the old key from updating in place.
- Never guess a keystore password or silently overwrite a candidate key.
- If the user explicitly authorizes rotation, warn about uninstall/reinstall,
  preserve the old file as a dated restricted backup, and generate the new key
  with an explicit alias and password.
- Never print, commit, or store passwords in tracked files. Keep local
  `key.properties` and `.jks` files ignored and mode 600 where possible.

## Verified workflow

1. Locate the intended keystore backup and inspect repository documentation,
   Gradle signing configuration, workflow inputs, and ignored paths.
2. Load the candidate keystore with `keytool` using a non-printing variable.
   Verify the store password and alias before creating local configuration or
   changing CI secrets. Key and store passwords may differ; verify each when
   the build configuration requires both.
3. Export the certificate and record only its SHA-256 fingerprint. Do not
   expose private-key material or password values.
4. For authorized rotation, generate a PKCS#12/RSA 2048 replacement with a
   stable explicit alias, then verify it before use. Back up the replacement
   immediately in a password manager or encrypted archive.
5. Create ignored local `android/key.properties` and place the keystore where
   the Gradle path expects it. Pass the alias explicitly in the CI workflow;
   do not rely only on an action default.
6. Replace the write-only GitHub secrets only after local verification:
   `ANDROID_RELEASE_KEYSTORE_BASE64` and
   `ANDROID_RELEASE_KEYSTORE_PASSWORD`. `gh secret list` verifies names and
   timestamps, not values.
7. Build the release APK, then compare the keystore certificate SHA-256 with
   `apksigner verify --print-certs` output. This artifact-level comparison is
   the end-to-end proof that Gradle used the intended key.
8. Clean up temporary logs and daemons, verify ignored signing files are not
   tracked, check `git diff --check`, and preserve the backup.

## Failure diagnosis

- `actual certificate: <missing>` usually means the APK was unsigned or debug
  signing/configuration was selected. If this persists across otherwise-correct
  keystore/secret rotation, check for two further causes before re-rotating
  anything: (1) Gradle silently falling back to `signingConfigs.debug` when the
  release signing config failed to load (missing `key.properties`, missing
  keystore file, or a decode failure) — make this fail closed instead: validate
  the decoded keystore, alias, and password exist and are non-empty *before*
  the build starts, and throw a `GradleException` rather than silently
  degrading to an unsigned/debug-signed artifact; (2) the CI verification
  step's own `apksigner verify --print-certs` output parser silently matching
  nothing. A single-line `awk`/`grep` against stdout only can miss the digest
  line if it lands on stderr or across a line wrap in that shell context —
  capture both stdout and stderr together and match any line containing
  `certificate SHA-256 digest:` rather than assuming a fixed stream/format.
- A nonmatching actual fingerprint means the wrong keystore, alias, or Gradle
  signing configuration was used.
- `actual certificate: <label text, not a hex digest>` (e.g. the verifier
  prints back its own field-name placeholder instead of a real fingerprint)
  means the parser matched a header/label string rather than the digest value.
  Restrict extraction to a strict 64-hex-character pattern (optionally
  colon-separated) and explicitly reject anything that doesn't match, rather
  than trusting whatever substring a naive `cut`/`awk` pulled out.
- A keytool password error means stop and locate the correct password or
  keystore; do not write an unverified value to GitHub.
- GitHub secrets cannot be read back. Verify the local artifact and let the CI
  signer-check step validate the secret payload on a real workflow run.

## Reusable reference

See `references/android-key-rotation-checklist.md` for a concise command
sequence that keeps password output out of logs.
