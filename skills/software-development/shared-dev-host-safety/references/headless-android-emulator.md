# Headless Android Emulator Verification

Use this on Linux hosts without a desktop display (CI, SSH, GPU workstations).

## Evidence-first diagnosis

1. Reproduce the exact Flutter path:
   `flutter emulators --launch <avd> -v`.
2. Capture the actual emulator command and complete stderr. The combination of
   exit `-6`, `elf_dynamic_array_reader`, `process_memory_range`, and no ADB
   device is not enough to blame the APK; inspect the preceding Qt/graphics
   messages.
3. Check KVM, memory, disk, AVD configuration, and kernel OOM/segfault logs.
4. Test the emulator binary independently with explicit headless flags.

## Known reliable probe

```bash
$ANDROID_HOME/emulator/emulator \
  -avd <avd> -no-window -no-audio -no-boot-anim -no-snapshot -gpu off
```

Wait for both `adb devices` to show `emulator-5554` and
`adb shell getprop sys.boot_completed` to return `1`. Cleanly stop it with
`adb emu kill`, then verify no emulator/qemu process remains.

On emulator 37.1.11, `-gpu off` is accepted and uses the SwiftShader renderer.
**Do not use `-gpu swiftshader_indirect`** on this version: it is not the
reliable flag, it can be silently accepted and still crash the emulator
process with a segfault shortly after boot (observed reproducibly, twice in a
row, on a boot that itself reported success) — `-gpu off` is the flag that has
actually been verified end-to-end through app install and launch.

## Flutter launcher limitation

`flutter emulators --launch` supplies only `-avd <name>`; it does not supply
`-no-window`, `-no-audio`, or a headless Qt platform. On a display-less host,
the normal launcher can therefore fail in Qt/XCB before Android starts even
when the AVD itself is healthy. Use the explicit emulator command above, then
run the app with `flutter run -d emulator-5554`. If a GUI path must be tested,
use a real display; Xvfb may remove the immediate Qt crash but still requires
independent ADB/boot verification.

## Post-boot crash: stop after two attempts, don't loop

A clean `boot_completed` does not guarantee the emulator process survives the
following app install/launch — it can still segfault with no compiler/app-level
error. If a second attempt (even with a different GPU flag) crashes the same
way, that is a real, reproducible host-level fault: stop retrying and report
it honestly rather than trying a third flag combination or presenting a crash
as a Portalis/app defect. Verifying the build/install/version-handshake up to
the point of the crash (APK built, installed, launched, correct version
strings logged) is legitimate partial evidence — cite exactly what you saw
and what you didn't, don't extrapolate to "the screen renders correctly."

## Cleanup pitfall

A failed launch can leave `multiinstance.lock`. Only remove that exact lock
after confirming no matching emulator/qemu process exists; never use a broad
`pkill` pattern that can match the cleanup shell or unrelated users' work.
