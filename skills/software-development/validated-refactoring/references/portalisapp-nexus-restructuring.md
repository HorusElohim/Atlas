# PortalisApp Nexus Module Restructuring (ADR-0003.5/ADR-0009)

This document captures the specific workflow and lessons learned from restructuring the PortalisApp Rust backend to move all internal modules under a `nexus` namespace, leaving only the API layer at the crate root.

## Overview

Following ADR-0004 naming discipline, all internal implementation details were moved under a `nexus` module, with only the API-facing components (`portalis_api`, `bridge`) remaining at the crate root level.

## Modules Moved

The following modules were moved from the crate root to under `nexus/`:
- core (including events, supervisor, nexus, torrents, transfers)
- collections
- store
- substrate
- torrent
- crypto (including crypto, crypto_capsule, crypto_keys, crypto_verify)
- device
- linked_source_store
- projection (including build, emit, state)
- domain (including identity)
- log
- paths
- settings
- vault

## Key Changes Made

### 1. Directory Structure
- Created `src/nexus/` directory
- Moved each module directory/file into `src/nexus/`
- Created `src/nexus/mod.rs` to re-export all internal modules
- Updated `src/lib.rs` to remove old module declarations and add `pub mod nexus;`

### 2. Import Updates
- Updated all internal imports throughout the codebase to use `crate::nexus::module::item` instead of `crate::module::item`
- Updated `src/bridge.rs` and `src/portalis_api.rs` to use the new paths
- Updated `tool/frb_build.sh` to include `crate::nexus::settings` and `crate::nexus::device` in the rust-inputs

### 3. Visibility Adjustments
- After moving modules, ensured types/functions that need to be accessed across modules have appropriate visibility:
  - Changed `pub(crate)` to `pub` for types that need to be accessed outside their module but within the crate
  - Example: Made `PeerHints` struct public in `src/nexus/substrate.rs`
  - Example: Made `Vault` struct and `named()` method public in `src/nexus/vault.rs`
  - Example: Made `DeviceId` and `KeyPair` public in `src/nexus/domain/identity.rs`

### 4. Flutter/Rust Bridge Regeneration
- After Rust API changes, ran `./tool/frb_build.sh` to regenerate Dart bindings
- Fixed Dart import paths in generated files to reflect the flattened module structure:
  - Changed imports from `nexus/device.dart` to `device.dart` when modules were flattened
  - Updated `lib/nexus/bridge/settings.dart` and `device.dart` to use correct API method names
  - Verified `frb_generated.dart`, `frb_generated.io.dart`, and `frb_generated.web.dart` have correct imports

### 5. Testing
- Ran full test suite: `cargo test` (211 tests passed)
- Ran Flutter tests: `flutter test` (all tests passed)
- Verified FRB generation: `./tool/frb_build.sh` completed without errors
- Ran project validation script: `./tests/nexus.sh` (passed after fixing formatting)

## Common Issues and Fixes

### Issue: "type X is more private than the item Y"
- Occurred when `pub` functions returned types with `pub(crate)` visibility
- Fixed by either:
  - Making the type `pub`: `pub struct RawStorageEntry { ... }`
  - Or changing the function to `pub(super)` if only needed by parent module

### Issue: Dart import errors after FRB regeneration
- Occurred when Flutter code tried to import from moved modules
- Fixed by:
  - Removing the `nexus/` subdirectory from `lib/nexus/bridge/` after FRB regeneration
  - Updating import paths in `settings.dart` and `device.dart` to import from the correct location
  - Ensuring `bridge.dart` imports the flattened modules correctly

### Issue: Missing FRB API methods
- Occurred when Rust function signatures changed but Dart bindings weren't updated
- Fixed by re-running `./tool/frb_build.sh` after any Rust API changes

## Verification Steps

1. **Build check**: `cargo build --release` should succeed with only warnings (no errors)
2. **Test suite**: `cargo test` should pass all tests
3. **Flutter tests**: `flutter test` should pass all tests
4. **FRB validation**: `./tool/frb_build.sh` should complete without errors
5. **Import check**: Verify no broken imports in Dart files after FRB regeneration
6. **Module structure**: Confirm `src/nexus/` contains all internal modules and only `api.rs`, `bridge.rs`, `lib.rs` remain at crate root
7. **API surface**: Verify that the public API (what Flutter sees) remains unchanged despite internal restructuring

## Lessons Learned

1. **Visibility is crucial**: When moving modules, pay close attention to which types need to be accessible across module boundaries
2. **FRB regeneration is mandatory**: Any change to the Rust API (including moving functions between modules) requires FRB regeneration
3. **Import paths matter**: After moving modules, every internal import in the codebase needs to be updated
4. **Test both sides**: Rust changes can break Dart bindings and vice versa - always test both
5. **Incremental approach**: Move one module at a time, updating imports and testing as you go, rather than moving everything at once
6. **Documentation helps**: Having clear module documentation in each `mod.rs` file makes it easier to understand the intended public API