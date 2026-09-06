# Apple mobile dependency target gates

## Reusable pattern

When upgrading a native/network Rust dependency, audit transitive crates for
Apple mobile targets. A predicate such as `#[cfg(not(target_os = "macos"))]`
usually means Linux in practice, but it also matches iOS/tvOS/visionOS and can
compile APIs unavailable on those platforms.

For an intentionally unsupported operation such as binding a socket to a
named network interface, patch the dependency locally through the workspace's
`[patch.crates-io]` section. Keep the existing macOS and Linux implementations
unchanged, and add an Apple-mobile implementation returning the dependency's
explicit `NotSupported` error. This is safer than a fake socket implementation
and preserves the rest of the network stack.

## Validation sequence

1. Copy/vendor the exact dependency version and remove registry-only metadata
   that the repository does not track.
2. Add the local path under `[patch.crates-io]`; regenerate `Cargo.lock`.
3. Run host formatting, check, and tests.
4. Run `cargo check --target aarch64-apple-ios --lib` (and other Apple targets
   when relevant).
5. If the target check reaches a build script and stops because the host lacks
   `xcrun` or the Apple SDK, report that separately: reaching past the original
   dependency source error proves the cfg fix was selected, but final iOS
   compilation still requires a Mac/Xcode environment.
6. Re-run the repository acceptance gate before committing.

## Portalis instance

`librqbit-dualstack-sockets 0.7.0` called `socket2::Socket::bind_device()` on
iOS because its non-macOS cfg included Apple mobile. Portalis now patches the
crate so iOS/tvOS/visionOS return `BindDeviceNotSupported`, while macOS keeps
indexed binding and Linux keeps named-device binding.
