# Python ROM — Lua shell parity checklist

Track progress toward **behaviorally equivalent** shell behavior vs stock **`lua/rom/programs/shell.lua`**, **`lua/bios.lua`** `read`, **`lua/rom/startup.lua`**, and related ROM modules.

**Convention:** `- [x]` = implemented / verified for this fork · Notes cite intentional gaps.

---

## A. Shell API (`shell.*`)

Reference: `data/computercraft/lua/rom/programs/shell.lua`

### Core execution

- [x] **`shell.run`** — tokenise → `shell.execute(first, …rest)`; empty → false (`cc.shell`)
- [x] **`shell.execute`** — resolves program; coerces arguments to **strings** (Lua `expect`); stack push; `.py` resolution (`Shell.execute`)
- [x] **Program stack** — `get_runningProgram` reflects outermost pushed path per `execute`
- [x] **`shell.exit`** — flag + BIOS shutdown path (`bios.py` / `shutdown.py`)

### Directory / path

- [x] **`shell.dir` / `shell.setDir`** — `setDir` takes resolved full path (matches Lua `fs.combine(dir,"")`)
- [x] **`shell.resolve`** — leading `/` absolute; else combine with `shell.dir()`
- [x] **`shell.path` / `shell.setPath`** — colon-separated PATH; ROM segments use **`/rom/...`** (see `startup.py`)

### Aliases

- [x] **`shell.setAlias` / `clearAlias` / `aliases`** — applied before `resolveProgram`

### Resolution / enumeration

- [x] **`shell.resolveProgram`** — aliases, explicit path, PATH walk, `.py` extension
- [x] **`shell.programs(include_hidden)`** — PATH directories, strip `.py`, skip dirs / `__init__` / hidden rules

### Completion

- [x] **`shell.complete`** — token index + trailing space; first-word `{ " " }`; handler suffix `+ " "`
- [x] **`shell.completeProgram`** — `fs.complete` + aliases + programs; `shell.autocomplete_hidden`
- [x] **`shell.setCompletionFunction` / `getCompletionInfo`** — keys are resolved ROM paths (`rom/programs/*.py`)

### Multishell (when API exists)

- [ ] **`shell.openTab` / `shell.switchTab`** — **N/A** in GraalPy Python VM today (no `multishell` global). Revisit when multishell is exposed to Python.

---

## B. Program execution environment

Reference: `shell.lua` `executeProgram`, `createShellEnv`

- [x] **`arg` / `arg[0]`** — list including command name at `[0]` for `execute` / hashbang chain
- [x] **Hashbang** — recursion limit 100; `shell.py` loop guard (Lua `shell.lua` parity)
- [x] **`shell` in env** — injected `Shell` API instance
- [x] **`require` / `package`** — Python uses ROM meta-path importer instead of `cc.require` — deep Lua `require` parity is a **separate milestone**

### Errors / strict globals

- [x] **`bios.strict_globals`** — `_StrictGlobals` dict when setting enabled (blocks new global assignments in program env)

---

## C. Interactive shell driver (`rom/programs/shell.py`)

Reference: tail of `shell.lua`

### Flow

- [x] **Argv mode** — runs `shell.run` without startup
- [x] **Interactive** — header; **`rom/startup`** only when `_parent is None`; **`await startup.run`**
- [x] **Prompt** — `shell.dir() .. "> "` on each redraw
- [x] **History** — append line if non-empty after strip; dedupe consecutive duplicates (aligned with Lua intent)

### Line input vs `_G.read`

- [x] **Completer** — gated by `shell.autocomplete`; uses module `shell.complete`
- [x] **Ghost completion** — end-of-line only; Tab / Right accept; Up/Down cycle vs history
- [x] **Enter** — redraw without ghost, then newline
- [x] **`paste`** — inserts pasted text at cursor (Lua `read`)
- [x] **NumPad Enter** — key **335** treated like Enter (`keys.lua`)
- [x] **`file_transfer`** — clears completion state + redraw (full Lua import flow **not** ported)
- [ ] **Password mask / default string / mouse reposition / horizontal scroll** — **not implemented** (documented gap vs full `bios.lua` `read`)

### Events

- [x] **`term_resize`** — redraw
- [x] **`terminate`** — `ShellExit` / Ctrl+T path

---

## D. Startup (`rom/startup.py`)

Reference: `lua/rom/startup.lua`

- [x] **PATH** — mirrors Lua segments using **`/rom/...`**; turtle vs rednet branch uses **`fs.is_dir("rom/programs/turtle")`** as stand-in for Lua’s `turtle` global; pocket/command appended when directories exist; **`http`** segment included like Lua
- [x] **Aliases** — baseline + **`bg`/`fg`** when colour (+ Python-only **`more` → `cat`**)
- [x] **`help.setPath`** — `cc.help.set_path("/rom/help")` (`cc/help.py` stub)
- [x] **Completion registrations** — all major programs that exist as **`.py`** in this ROM (plus monitor simplified vs Lua’s third `many` block)
- [x] **ROM autorun** — `rom/autorun/*` non-dot files
- [x] **MOTD** — `shell.run("motd")` when `motd.enable`
- [x] **User startup** — `startup` file or `startup/` directory at root via `shell.resolve` + `fs`
- [ ] **Disk startup** — Lua uses **`peripheral`/`disk`** to scan mounted disks — **not** wired for Python yet

---

## E. Settings

Reference: `bios.lua` + `rom/apis/settings.lua`

- [x] **Defaults** — `cc.settings` mirrors BIOS `settings.define` keys
- [x] **Persistence** — `settings.load()` / `settings.save()` using **JSON** at **`.settings`** (Lua uses `textutils.serialize` — **on-disk format differs**, merge semantics aligned)

---

## F. Shared libraries used by shell UX

- [x] **`fs.complete`** — ported from Lua ROM `fs.lua`
- [x] **`cc.shell.completion`** — aligned with Lua where helpers exist; peripheral/command/help completions still **stubs** where noted in source
- [x] **`cc.completion`** — choice/side helpers used by shell completion

---

## G. ROM programs inventory

Stock Lua **`rom/programs`** is larger than the Python preview tree. Policy for **1:1 coverage**:

| Area | Lua programs (examples) | Python status |
|------|-------------------------|---------------|
| Root utilities | `cd`, `list`, `copy`, `move`, … | **Ported** (see `python/rom/programs/*.py`) |
| HTTP | `http/wget`, `http/pastebin` | **Missing** — add when HTTP bridge is ready |
| Rednet | `rednet/chat`, `rednet/repeat` | **Missing** |
| Advanced | `advanced/fg`, `advanced/bg`, `multishell` | **Missing** (depends on multishell) |
| Turtle / Pocket / Command | subtree | **Missing** / environment-specific |
| Fun | `fun/*` | **Missing** except what you add |

Completion entries in **`startup.py`** only reference **existing** `.py` files (plus stubs implied above).

---

## H. Automated tests

- [x] **`PythonMachineTest`** — imports, tokenise, settings defaults (`gradlew :core:test --tests …PythonMachineTest`)
- [ ] **Optional** — dedicated FS mock tests for `resolveProgram` / PATH (future)

---

## I. Intentional differences

- [x] **Extension** — `.py` instead of `.lua`
- [x] **`cat`** — Python convenience (not stock Lua ROM); alias **`more`** → **`cat`**
- [x] **Guest `fs.open`** — prefer **`fs.read_all`** / host bridge for reliability under GraalPy

---

## Quick audit commands (local)

```bash
.\gradlew.bat :core:test --tests "dan200.computercraft.core.python.PythonMachineTest"
```

Diff ROM trees: `lua/rom/programs` vs `python/rom/programs`.

---

*Last updated: parity sweep — multishell / disk startup / full Lua ROM program set remain follow-up work.*
