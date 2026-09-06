# Generated collection DTOs in test seams

FRB may map Rust collection fields to typed Dart collections rather than `List<T>` (for example, `Vec<u32>` can become `Uint32List`). Do not assume a list literal satisfies a generated DTO constructor.

When updating a repository/controller contract:

1. Regenerate bindings before editing adapter code.
2. Inspect the generated Dart DTO field type.
3. Construct the declared typed collection in production and test-seeding code, e.g. `Uint32List.fromList([collectionId])`.
4. Update every `AppRepository` fake with a truthful empty response for the new call; test seed helpers may adapt older live fixtures into the new aggregate DTO solely for test compatibility.
5. Verify a widget test that reaches the actual controller method, not merely a screen built from hand-made view models.

For endpoint telemetry, aggregate in Rust first. The Flutter adapter may map collection handles to display names, but it must not sum counters, choose saved-versus-live totals, or deduplicate endpoint identities.