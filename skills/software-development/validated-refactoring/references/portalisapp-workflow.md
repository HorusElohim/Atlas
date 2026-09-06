# PortalisApp Refactoring Workflow

Project-specific commands and conventions for validated refactoring in the PortalisApp codebase.

## Commands

### Rust (Backend)
```bash
cd portalis/rust/backend
CARGO_BUILD_JOBS=2 cargo fmt --all
CARGO_BUILD_JOBS=2 cargo check -p backend --lib
CARGO_BUILD_JOBS=2 cargo clippy --workspace --all-targets --all-features -- -D warnings
CARGO_BUILD_JOBS=2 cargo test -p backend --lib
CARGO_BUILD_JOBS=2 cargo test --workspace --all-targets --all-features
```

### Validation Script
```bash
cd /home/elohim/PortalisApp
./tests/nexus.sh
```

### Flutter (Dart)
```bash
cd portalis
dart format .
flutter_rust_bridge_codegen generate \
  --rust-root ../portalis/rust/backend \
  --rust-input crate::bridge,crate::portalis_api,crate::device,crate::settings \
  --dart-output ../lib/nexus/bridge \
  --rust-output ../portalis/rust/backend/src/api.rs \
  --no-add-mod-to-lib
# Or use the helper script:
./tool/frb_build.sh
```

## Version Files
- `portalis/pubspec.yaml` - Flutter version
- `portalis/rust/backend/Cargo.toml` - Rust backend version
- `CHANGELOG.md` - changelog entries under `## Unreleased`

## Commit Style
- `🐛 fix: ...` - bug fixes
- `✨ feat: ...` - new features
- `📚 docs: ...` - documentation
- `🧹 chore: ...` - maintenance

## Common Patterns

### Dead Code Removal
1. Search: `git grep -n 'allow(dead_code)\|unused_import'`
2. Check usage: `git grep -n 'TypeName\|function_name' -- '*.rs'`
3. Delete if truly unused (including the `#[allow(...)]` attribute)
4. For test-only utilities: keep with `#[allow(dead_code)]` but document why

### FRB Bindings
After Rust API changes:
1. Update `frb_build.sh` rust-inputs if modules added/removed
2. Run `./tool/frb_build.sh`
3. Check generated `lib/nexus/bridge/frb_generated.dart` and `src/api.rs`

## File Locations
- Rust crate root: `portalis/rust/backend/`
- Flutter app root: `portalis/`
- Validation script: `tests/nexus.sh`
- FRB tool scripts: `portalis/tool/`