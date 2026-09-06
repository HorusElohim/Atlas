# Self-producing framework cycles

When an Xcode script phase creates an XCFramework that the same native target links or embeds, declaring the XCFramework in `outputPaths` is not enough. Xcode can still form a cycle through the framework directory signature:

```text
ProcessXCFramework -> generated.xcframework directory signature
  -> producer script phase -> target gate -> ProcessXCFramework
```

## Durable repair

Move the producing `PBXShellScriptBuildPhase` to a dedicated `PBXAggregateTarget` (for example `RustBackend`). Remove that phase from the consuming target, add a `PBXContainerItemProxy` plus `PBXTargetDependency`, and register the aggregate target in the project. Give it every project configuration (Debug, Release, Profile), with the deployment target and code signing disabled for the aggregate.

Keep the consumer's framework file reference, link phase, embed phase, `CodeSignOnCopy`, signing phase, and native networking configuration unchanged. The consumer then depends on a completed upstream artifact instead of producing and consuming the artifact in one target.

## Verification

1. Check balanced braces and parentheses in `project.pbxproj`.
2. Parse the object graph and confirm the producer phase appears only under the aggregate target.
3. Confirm the consumer target depends on the aggregate target.
4. Clear the Mac's DerivedData before the first real retry; a warm build can hide a latent graph cycle.
5. Report structural validation separately from the required native Xcode build; Linux cannot prove the final iOS build.
