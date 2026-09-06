# Android key rotation checklist

```bash
set -euo pipefail
keystore="$HOME/secrets-portalis/portalis-release.jks"
umask 077
read -rsp 'Keystore store password: ' KEYSTORE_PASSWORD
printf '\n'
keytool -list -keystore "$keystore" -alias portalis \
  -storepass "$KEYSTORE_PASSWORD" >/dev/null
fingerprint=$(keytool -exportcert -rfc -keystore "$keystore" \
  -alias portalis -storepass "$KEYSTORE_PASSWORD" |
  openssl x509 -noout -fingerprint -sha256 |
  cut -d= -f2 | tr -d ':[:space:]' | tr '[:lower:]' '[:upper:]')
printf 'alias=portalis\ncertificate=%s\n' "$fingerprint"
unset KEYSTORE_PASSWORD
```

For an explicitly authorized rotation:

1. Move the old candidate to a dated restricted backup.
2. Generate the replacement with `keytool -genkeypair -storetype PKCS12`.
3. Verify its alias and fingerprint.
4. Base64 the replacement directly into
   `gh secret set ANDROID_RELEASE_KEYSTORE_BASE64`; set the password with
   `gh secret set ANDROID_RELEASE_KEYSTORE_PASSWORD -b ...`.
5. Build the APK and compare its `apksigner --print-certs` SHA-256 with the
   verified keystore fingerprint.
6. Keep the replacement backup outside Git and document the rotation and
   reinstall consequence without documenting the password.
