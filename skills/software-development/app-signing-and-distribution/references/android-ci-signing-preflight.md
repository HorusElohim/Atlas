# Android CI signing preflight

Use this before changing GitHub signing secrets or diagnosing an APK signer
mismatch. Keep output limited to status and certificate fingerprints; never
print passwords or base64 keystore data.

## 1. Verify a candidate keystore locally

```bash
set -euo pipefail
keystore="$HOME/secrets-portalis/portalis-release.jks"
read -rsp 'Keystore store password: ' KEYSTORE_PASSWORD
printf '\n'
keytool -list \
  -keystore "$keystore" \
  -alias portalis \
  -storepass "$KEYSTORE_PASSWORD" >/dev/null
fingerprint=$(keytool -exportcert -rfc \
  -keystore "$keystore" -alias portalis \
  -storepass "$KEYSTORE_PASSWORD" |
  openssl x509 -noout -fingerprint -sha256 |
  cut -d= -f2 | tr -d ':[:space:]' | tr '[:lower:]' '[:upper:]')
printf 'alias=portalis certificate=%s\n' "$fingerprint"
unset KEYSTORE_PASSWORD
```

Do not overwrite a known-good repository secret until this verification passes.
A key password can differ from the store password; verify the exact values used
by the Gradle configuration.

## 2. Install CI inputs without relative-path ambiguity

The action should decode the secret, validate the file and alias, and write
`key.properties` with an absolute path:

```bash
echo "$KEYSTORE_BASE64" | base64 -d > android/app/portalis-release.jks
test -s android/app/portalis-release.jks
keytool -list -keystore android/app/portalis-release.jks \
  -alias "$KEYSTORE_ALIAS" -storepass "$KEYSTORE_PASSWORD" >/dev/null
cat > android/key.properties <<EOF
storePassword=$KEYSTORE_PASSWORD
keyPassword=$KEY_PASSWORD
keyAlias=$KEYSTORE_ALIAS
storeFile=$(pwd)/android/app/portalis-release.jks
EOF
test -s android/key.properties
```

Use an absolute `storeFile` because Gradle's `file(...)` resolution is relative
to the Android module/project context and a relative path can silently select a
missing file, causing a fallback signing configuration.

## 3. Verify the artifact

```bash
apk=build/app/outputs/flutter-apk/app-release.apk
expected=$(keytool -exportcert -rfc \
  -keystore android/app/portalis-release.jks \
  -alias "$KEYSTORE_ALIAS" -storepass "$KEYSTORE_PASSWORD" |
  openssl x509 -noout -fingerprint -sha256 |
  cut -d= -f2 | tr -d ':[:space:]' | tr '[:lower:]' '[:upper:]')
apksigner="$ANDROID_HOME/build-tools/<version>/apksigner"
actual=$("$apksigner" verify --print-certs "$apk" |
  awk -F': ' '/Signer #1 certificate SHA-256 digest:/{print $2; exit}' |
  tr -d ':[:space:]' | tr '[:lower:]' '[:upper:]')
test -n "$actual" && test "$expected" = "$actual"
printf 'APK signer verified: %s\n' "$actual"
```

A blank actual digest means the APK is not signed in the expected way. Do not
repair this by accepting the blank value or by lowering the verification gate;
fix the Gradle input path/configuration and rerun.

## 4. Rotate only with explicit authorization

Generate a replacement only after confirming the old identity is unrecoverable.
Preserve the old keystore as a dated, access-controlled backup, generate the
new key once, update both GitHub secrets, and back up the new keystore and its
password in a password manager. Record the new public certificate fingerprint,
not the password. Existing old-key installations cannot receive updates from
the replacement identity and need an uninstall/reinstall transition.