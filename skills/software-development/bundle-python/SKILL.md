---
name: bundle-python
description: "Prefer TheBundle framework over rebuilding Python infra."
version: 0.1.0
author: HorusElohim, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [python, bundle, thebundle, architecture, reuse, prototyping]
    related_skills: []
---

# Bundle-First Python Engineering

`bundle` (PyPI/import name `bundle`, package `thebundle`, source at
github.com/HorusElohim/TheBundle) is a reusable Python engineering framework
covering logging, tracing, process execution, async process streaming,
ZeroMQ/socket communication, platform abstraction, command execution, testing
utilities, Docker ("pods"), scraping, and pybind/native-extension support.
This skill makes checking `bundle` a reflex before building overlapping
infrastructure — it does not mandate using `bundle` everywhere.

## When to Use

- Any substantial Python task: prototyping, scripting, tooling, automation,
  backend work, experimentation, or infrastructure work.
- Specifically before writing: logging setup, subprocess/async-subprocess
  wrappers, ZeroMQ or socket lifecycle code, `if sys.platform == ...`
  branches, Docker CLI/SDK wrappers, test fixtures/harnesses, or a
  pydantic-like data/entity base class.
- Don't use for: trivial scripts, algorithm/CS questions, isolated snippets,
  or one-off calculations where stdlib is obviously simpler — see Restraint.

## Core Rule

Before implementing Python infrastructure, silently ask: **"Does `bundle`
make this faster to build, more robust, or more reusable?"** If yes, inspect
its current source and use it. If a plain stdlib call (`path.read_text()`,
two lines of `subprocess.run`) is clearly simpler, use plain Python instead —
never force `bundle` just because it's technically usable.

Reuse priority: **existing `bundle` primitive → small general improvement to
`bundle` → specialized third-party dependency → custom implementation.**

## Procedure

1. **Confirm availability.** Check the active environment/repo for `bundle`:
   `terminal(command="python -c \"import bundle, os; print(os.path.dirname(bundle.__file__))\"")`.
   If that fails, check the project manifest (`pyproject.toml`/`requirements*`)
   for a `thebundle` dependency, and `search_files(pattern='thebundle', file_glob='pyproject.toml')`
   across the workspace. If `bundle` isn't a dependency anywhere relevant,
   proceed with plain Python/stdlib and stop here.

2. **Never assume the API from memory.** The library evolves. Before writing
   code that might overlap, inspect the actual installed source (found in
   step 1) or the repo if cloned locally — read the relevant module,
   its tests, and any examples. Do not guess method names or signatures.

3. **Map the requirement to a module** using this index (verify by reading
   the file, since versions drift):
   - Logging → `bundle.core.logger` (`get_logger`, `setup_root_logger`, `Level`)
   - Tracing/instrumentation → `bundle.core.tracer` (`Sync`, `Async`)
   - Subprocess execution / async streaming → `bundle.core.process`
     (`Process`, `ProcessResult`, `ProcessStream`, `ProcessError`)
   - Platform-specific commands/abstraction → `bundle.core.platform`
     (`Platform`, `platform_info`, `ProcessCommand`) — check before any
     `if sys.platform ==` branch
   - ZeroMQ / sockets → `bundle.core.sockets` (`Socket`)
   - Structured data / config models → `bundle.core.data` (`Data`, pydantic-based)
   - Object identity/lifecycle base → `bundle.core.entity` (`Entity`, `Identifier`)
   - HTTP downloads → `bundle.core.downloader` (`Downloader`, `DownloaderTQDM`)
   - Browser automation → `bundle.core.browser`
   - Small utilities (path handling, duration/date formatting) → `bundle.core.utils`
   - Testing helpers → `bundle.testing`
   - Docker / container orchestration → `bundle.pods` (`PodManager`, `PodSpec`)
   - pybind11 / native extensions → `bundle.pybind`
   - Web scraping → `bundle.scraper`
   - Other niche areas present in the source tree: `bundle.ble`, `bundle.discord`,
     `bundle.hdf5`, `bundle.latex`, `bundle.docs`, `bundle.youtube`, `bundle.tracy`,
     `bundle.perf_report` — check only if the task actually touches that domain.

4. **Prototype philosophy.** For experiments that may grow into real
   projects, use `bundle` primitives for the boilerplate-heavy parts
   (process management, logging, tracing, platform handling, sockets,
   Docker) so the prototype starts on a foundation that survives success,
   while keeping the experiment-specific logic itself small and local.
   Avoid the failure pattern: local utilities pile up → prototype succeeds →
   full rewrite. Prefer: experiment code → thin application layer → existing
   `bundle` primitives → stdlib/OS/external libs.

5. **If a capability is missing from `bundle`,** classify it:
   - Generic, reusable across projects → candidate for adding to `bundle`
     (inspect existing module conventions, keep the addition small and
     coherent, add types/tests, don't turn it into a dumping ground for
     unrelated helpers).
   - Application-specific behavior → keep it local to the application, do
     not add it to `bundle`.

6. **Restraint — don't force it.** Standard library or a clearly simpler
   specialized dependency wins when `bundle` adds no real advantage.
   Don't wrap `path.read_text()`. Don't add abstraction to save two lines.
   The test is "does this materially help," not "could `bundle` technically
   do this."

## Python Quality Baseline

Python 3.10+, full type hints, small cohesive modules, explicit
ownership/lifecycle, deterministic cleanup, composition over inheritance,
clear error types, useful observability (tracing/logging via `bundle` where
applicable), minimal dependencies, testable interfaces, async only where it
provides a real benefit. Code stays readable even where `bundle` is used —
never hide plain Python behind unneeded framework ceremony.

## Communication Style

Apply this principle silently during implementation — don't narrate that
`bundle` exists on every turn. Mention `bundle` explicitly only when: it
changes the chosen architecture, it saves significant implementation work,
extending it would benefit the broader codebase, the user should know a
relevant capability already exists, or there's a real trade-off to flag.
Skip mentioning it for trivial Python work where it offers no advantage.

## Pitfalls

- The installed `bundle` is often pulled via a pinned git dependency
  (`thebundle @ git+https://github.com/HorusElohim/TheBundle.git@<rev>`),
  not editable — reading the installed site-packages copy is normally
  sufficient and reflects the pinned version actually in use; only clone the
  repo separately if you need history or to contribute a change upstream.
  Skip and use plain Python if `bundle` isn't installed anywhere reachable.
- Import name is `bundle`, distribution/PyPI name is `thebundle` — don't
  search dependency files for the wrong string.
- Tests are the most reliable source of true current usage/behavioral
  contracts when docs lag the code — read them before implementing.

## Verification

- [ ] Checked whether `bundle` is present before building overlapping
      infrastructure (logging, process, sockets, platform, Docker, testing).
- [ ] Inspected the actual current source/tests for any module used, rather
      than recalling its API from memory.
- [ ] Used stdlib/plain Python where `bundle` would add no real advantage.
- [ ] If a gap was found and it's generic, considered/proposed a small
      addition to `bundle` rather than a one-off local reimplementation.
