---
name: xcode-build-graph-repair
description: "Use for Xcode dependency cycles and pbxproj repair."
version: 1.0.0
---

# Xcode Build Graph Repair

Use when an Xcode/Flutter-iOS/macOS build fails with a build-graph error rather than a
compile error: `Cycle inside <Target>`, "That command depends on command in Target X:
script phase Y", phases running in the wrong order, or an embedded framework that is
missing on a clean build but present on a warm one.

This is project-file surgery on `*.xcodeproj/project.pbxproj`, and it is routinely done
from a non-Mac host. The graph is fully analyzable offline; only the final build is not.

## Phase 1 — Read the cycle trace as a graph, not as prose

Xcode prints the cycle as a chain. Walk it backwards from `CYCLE POINT` and identify:

- the **consumer** command (`ProcessXCFramework`, `PBXCopyFilesBuildPhase`, `Ld`, ...)
- the **producer** node (a `PhaseScriptExecution`, a `MkDir`, a generated file)
- the **target** each one belongs to

The near-universal root cause: **one target both produces and consumes the same artifact.**
A script phase inside target T writes a file that T also references as a linked/embedded
`PBXFileReference`. Xcode takes a `directoryTreeSignature` of that path when planning T,
which depends on the script, which depends on T's own gate node → cycle.

Classic shape:

```
Runner:MkDir .../Runner.app/Frameworks
  → Gate Runner--immediate
    → build/.../backend.framework  (ProcessXCFramework)
      → ios/Frameworks/backend.xcframework      ← directoryTreeSignature
        → PhaseScriptExecution "Build Rust (iOS)"  ← SAME target
          → Runner--immediate                      ← CYCLE
```

## Phase 2 — Explain why it appeared "after an upgrade"

Do not accept "the upgrade broke it" without a mechanism. A latent producer/consumer
cycle is frequently masked by a **stale artifact on disk**: when the output already
exists and is up to date, Xcode can short-circuit the signature check. A `cargo clean`,
`flutter clean`, DerivedData wipe, or fresh clone removes the mask and the real graph
defect surfaces. Say this explicitly — it tells the user the bug predates the upgrade.

## Phase 3 — Fix: move the producer out of the consumer target

The correct fix is almost never reordering phases or deleting the file reference. It is:

1. Create a `PBXAggregateTarget` (e.g. `RustBackend`, `GenerateAssets`) whose *only*
   build phase is the producing script phase — move the existing
   `PBXShellScriptBuildPhase` object wholesale, keeping its UUID.
2. Remove that phase UUID from the consumer target's `buildPhases`.
3. Add a `PBXContainerItemProxy` (proxyType 1, `remoteGlobalIDString` = aggregate target
   UUID) + a `PBXTargetDependency`, and list the dependency UUID in the consumer's
   `dependencies`.
4. Register the aggregate target in `PBXProject.targets`.
5. Give the aggregate its own `XCConfigurationList` with **every** configuration the
   project defines (Debug/Release/Profile — Flutter projects have three, not two), each
   carrying at minimum `SDKROOT`, the deployment-target key, and
   `CODE_SIGNING_ALLOWED = NO` / `CODE_SIGNING_REQUIRED = NO`.

The consumer now sees the artifact as pre-existing input produced by an upstream target,
so the graph is a DAG. Schemes with `buildImplicitDependencies = "YES"` pick this up with
no scheme edit.

### Do not "fix" it by amputating the feature

Removing the framework reference, disabling embedding, dropping code signing, or turning
off a networking/entitlement feature to make the graph resolve is a regression disguised
as a fix. Preserve the linking + embed + `CodeSignOnCopy` + signing topology exactly and
state in the summary that you did.

## Phase 4 — Verify the edit structurally (works from Linux)

Never eyeball a pbxproj diff. Two mechanical checks:

```bash
python3 - <<'EOF'
import re
s = open("ios/Runner.xcodeproj/project.pbxproj").read()
print("braces:", s.count("{") == s.count("}"))
print("parens:", s.count("(") == s.count(")"))
ids  = set(re.findall(r'^\t\t([0-9A-F]{24}) /\*', s, re.M))
refs = set(re.findall(r'\b([0-9A-F]{24})\b', s))
print("referenced-but-undefined:", sorted(r for r in refs if r not in ids))
EOF
```

(`mainGroup`'s UUID legitimately shows as "undefined" by this heuristic — it is defined in
`PBXGroup` without a trailing comment. Anything else in the list is a real dangling ref.)

Then parse the real object graph — see `scripts/dump_xcode_targets.py`:

```bash
python3 -m venv /tmp/pbx && /tmp/pbx/bin/pip install -q pbxproj
/tmp/pbx/bin/python scripts/dump_xcode_targets.py ios/Runner.xcodeproj/project.pbxproj
```

Confirm the producing phase is listed under the aggregate target and **absent** from the
consumer, and that the consumer's `deps:` names the aggregate.

## Phase 5 — Report honestly

You cannot build iOS/macOS from Linux. Structural validation is not build validation.

- State plainly: "I have not built this; there is no Xcode on this host."
- Hand the user the exact command sequence, and **always** include the DerivedData wipe —
  the stale cycle graph is cached there and a re-run without it can reproduce the old error:

```bash
rm -rf ~/Library/Developer/Xcode/DerivedData/<Target>-*
./tool/run.sh ios --release --device <Device>
```

- Ask for raw output on failure. Do not declare the native fix complete without device or
  build evidence.

## Pitfalls

- Editing the pbxproj with `sed`/regex across object boundaries corrupts it silently.
  Use anchored unique-context replacements and re-run the balance check.
- Reusing an existing UUID for a new object, or inventing one that collides, produces
  bewildering Xcode errors. Derive new UUIDs from an unused prefix in the same family.
- Omitting the `Profile` configuration on the new aggregate target breaks
  `flutter build --profile` only — easy to miss until much later.
- CocoaPods regenerates `Pods-*.xcconfig` and its own project, but does **not** rewrite
  `Runner.xcodeproj`; a `pod install` will not undo or fix this edit.
- `alwaysOutOfDate = 1` on the script phase does not prevent the cycle — the signature
  dependency exists regardless.

## References

- `references/portalis-ios-rust-xcframework-cycle.md` — the full worked Portalis case:
  original cycle trace, exact pbxproj objects added, verified target graph.
- `scripts/dump_xcode_targets.py` — print every target, its isa, dependencies, and build
  phases from a pbxproj.
