#!/usr/bin/env python3
"""Dump every target in an Xcode project: isa, dependencies, build phases.

Use to verify a pbxproj edit structurally from any host (no Xcode required).

Setup:
    python3 -m venv /tmp/pbx && /tmp/pbx/bin/pip install -q pbxproj

Usage:
    /tmp/pbx/bin/python dump_xcode_targets.py ios/Runner.xcodeproj/project.pbxproj

Read the output for:
  - a producing script phase listed under its own PBXAggregateTarget,
  - that same phase ABSENT from the consuming native target,
  - the consumer's deps naming the aggregate.
"""

import sys

from pbxproj import XcodeProject


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    project = XcodeProject.load(sys.argv[1])

    for target in project.objects.get_targets():
        deps = []
        for dep_id in getattr(target, "dependencies", None) or []:
            dep = project.objects[dep_id]
            deps.append(project.objects[dep.target].name)
        print(f"{target.name} | {target.isa} | deps: {deps}")
        for phase_id in target.buildPhases:
            phase = project.objects[phase_id]
            print(f"    - {phase.isa} {getattr(phase, 'name', '')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
