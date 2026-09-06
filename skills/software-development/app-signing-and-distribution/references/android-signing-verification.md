# Android signing verification

Use this sequence when a release APK reports a signer mismatch:

1. Locate the intended long-lived keystore backup; never generate a replacement
   for an existing app identity.
2. Verify the store password with `keytool -list` before using the alias.
3. Export the alias certificate and normalize its SHA-256 fingerprint.
4. Compare it with the expected upload certificate.
5. Only after those checks pass, create ignored `android/key.properties` or set
   write-only CI secrets.
6. Build the release APK and read its signer using `apksigner verify
   --print-certs`; compare the artifact fingerprint again.

A missing APK certificate usually means the local build fell back to debug or
unsigned output. A keytool password failure is not evidence that the alias is
wrong: the keystore must load first, and store and key passwords may differ.
Do not guess passwords, replace the keystore, or overwrite CI secrets after an
unverified check. Keep all successful output limited to alias, status, and
fingerprint; never print passwords or keystore contents.
