# Generated-output hygiene

## Normalization rule

A successful FRB generator exit does not prove the generated Rust is ready to
commit. Some codegen versions emit valid imports in an order that
`cargo fmt --check` rejects.

**Reliable fix:** put `cargo fmt --all` immediately after code generation in
the repository helper, then rerun the helper. Do not hand-edit generated
`api.rs`; the next generation would overwrite the manual change.

## Review order

1. Inspect the generator's explicit Rust inputs. Prefer small app-facing
   modules over a crate-wide scan in a complex workspace.
2. Regenerate once and inspect the changed generated Dart/Rust files.
3. Run the format gate and compile/test the generated Rust.
4. Update application adapters and every fake implementing an expanded bridge
   interface.

## Diagnostics

Duplicate internal type names and unsupported private shapes are advisory only
when they remain outside exported FRB signatures. Treat them as a boundary
problem if they appear in generated public DTOs or cause generated Rust to
fail compilation; fix the app-facing Rust API rather than suppressing logs.
