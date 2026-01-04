# DevTrace: Local-First Provenance for AI-Augmented Dev

## Problem
- Agents and humans both run commands, edit files, and call tools, but repos rarely track *how* changes happened—only final diffs.
- Reviewers can’t easily answer “What did the agent change, in what order, and why?” from git history alone.
- Existing observability (Langfuse/Phoenix) targets services, not shells/IDEs; MCP gateways watch network/tool access, not repo-local provenance.

## What DevTrace Does
- Records **sessions** (traces) of work inside a repo and **events** (spans) like `run_command`, `edit_files`, `git_snapshot`, `mcp_call` (planned proxy), and `note`.
- Stores everything locally in `.devtrace/` (SQLite/JSONL), with optional global stats in `~/.devtrace/`.
- Provides a CLI to list sessions, show timelines, and follow events live; later adds a local MCP surface so agents can query provenance safely.

## Why Start with a Python CLI
- Fast iteration and a broad contributor base; rich tooling for shells/pty, git, and tests.
- Easy to layer future semantic search/redaction (embeddings, heuristics) before exposing data to agents.
- Packaging is fine for dev (`pip install -e .[dev]`); binary-like bundles can follow (shiv/pex/uv).

## Architecture (initial)
- **Core**: Python 3.11+, Typer CLI, SQLite store under `.devtrace/`.
- **Ingestion v0.1**: shell wrapper `devtrace shell --agent <name>`, git snapshots `devtrace snapshot --label "<msg>"`, manual notes.
- **Queries**: `sessions`, `show --session <id>`, `log --follow`, filters by event type/agent/time.
- **Planned v0.2**: MCP proxy to log `call_tool` traffic; local MCP server exposing `list_sessions`, `list_events`, `get_diff`, `search_commands`; optional TUI/web view.

## Roadmap
- **v0.1 (CLI-only)**: stable event schema; session lifecycle; shell wrapper logging; snapshots; notes; basic stats; local-only storage.
- **v0.2 (MCP surface)**: MCP proxy + query tools; redact/sanitize outputs for agent consumption; structured search APIs.
- **v0.3+**: semantic indexing of events/diffs; exports to Langfuse/Phoenix; policy hooks (retention, redaction), richer UI.

## Quickstart (planned)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
devtrace init
devtrace shell --agent cline        # or continue/claude-code/manual
devtrace snapshot --label "refactor billing"
devtrace log --follow               # tail events
devtrace show --session <id>
```

## Contributing
- Keep code under `devtrace/`, tests under `tests/`; never commit `.devtrace/` data.
- Style: type-hinted Python, 4-space indents; `ruff check .` and `ruff format .`; `pytest` for tests.
- Commits: imperative, concise subjects; PRs: include rationale and sample CLI output/logs when fixing behavior.

Absolutely, let’s build a **single, coherent mental model** of this whole thing: PTYs, FIFO, hooks, DevTrace – all of it working together.

Think of it as a **stack of layers + two separate “pipes”**:

* An **interactive pipe** (PTYs) for what you see & type
* A **logging pipe** (FIFO) for structured CMD/EXIT events

I’ll walk through:

1. The players
2. The two channels (PTY vs FIFO)
3. The exact lifecycle when you run a command
4. A final “picture in your head” summary

---

## 1. The main players

### 1. iTerm (outer terminal)

* When you open iTerm, it asks the kernel for a PTY pair (pseudo-terminal) – a **master/slave** device.
* iTerm holds the **master** side; the kernel exposes the **slave** as something like `/dev/ttysXYZ` or `/dev/pts/0`.
* It then starts your **login shell** (bash/zsh) with its stdin/stdout/stderr attached to that **slave**.

So:

```text
YOU ↔ iTerm ↔ PTY₀ master ↔ PTY₀ slave ↔ login shell
```

### 2. DevTrace (Python wrapper)

You run inside that login shell:

```bash
python devtrace.py
```

* DevTrace is just a **program running inside iTerm’s shell**.
* It inherits stdin/stdout from the login shell → which are attached to **PTY₀ slave**.

### 3. DevTrace’s own PTY (inner PTY)

Inside `devtrace.py`, it does:

* `pty.spawn([user_shell, "-l"], env=env_with_hooks)`

`pty.spawn` (under the hood) creates another PTY pair (**PTY₁**), forks, and:

* Child process:

  * stdin/stdout/stderr → **PTY₁ slave**
  * `execve(user_shell, ["bash", "-l"], env_with_hooks)`
* Parent (DevTrace) keeps **PTY₁ master** and runs a loop:

  * read from DevTrace’s stdin (PTY₀ slave) → write to PTY₁ master
  * read from PTY₁ master → write to DevTrace’s stdout (PTY₀ slave)

So now there is:

```text
YOU
  ↕
iTerm
  ↕
PTY₀ master ↔ PTY₀ slave ↔ DevTrace (Python, pty.spawn)
                               ↕
                          PTY₁ master ↔ PTY₁ slave ↔ child shell (instrumented bash/zsh)
```

iTerm only knows about PTY₀.
DevTrace is bridging between PTY₀ and PTY₁.

### 4. FIFO (named pipe)

Before spawning the shell, DevTrace does something like:

```python
os.mkfifo("/tmp/devtrace_cmd_<pid>")
env["DEVTRACE_FIFO"] = "/tmp/devtrace_cmd_<pid>"
```

* `mkfifo` creates a **named pipe (FIFO)** in the filesystem: a special file that behaves like a pipe, not a normal file.
* Multiple processes can open it; writers `write()` bytes into it, readers `read()` bytes out in the same order (First In, First Out).

Then DevTrace starts a background thread:

```python
with open(DEVTRACE_FIFO, "r") as f:
    for line in f:
        parse CMD/EXIT lines
```

This is the **FIFO reader** – it just blocks on `read()` and wakes up when the shell writes something.

### 5. Shell hooks

Inside the child shell (running on PTY₁ slave), DevTrace arranges to load hooks, for example in bash:

```bash
# Only enable if DEVTRACE_FIFO is set
if [[ -n "$DEVTRACE_FIFO" ]]; then
  _devtrace_preexec() {
    printf 'CMD %s %s\n' "$(date +%s)" "$BASH_COMMAND" >>"$DEVTRACE_FIFO"
    _DEVTRACE_CMD_START=$SECONDS
  }

  _devtrace_precmd() {
    local ec=$?
    local dur_ms=$(( (SECONDS - _DEVTRACE_CMD_START) * 1000 ))
    printf 'EXIT %s %s %s %s\n' "$(date +%s)" "$ec" "$dur_ms" "$PWD" >>"$DEVTRACE_FIFO"
  }

  trap '_devtrace_preexec' DEBUG
  PROMPT_COMMAND="_devtrace_precmd; $PROMPT_COMMAND"
fi
```

* `DEBUG` trap → calls `_devtrace_preexec` **before each command**.
* `PROMPT_COMMAND` → calls `_devtrace_precmd` **after each command**, before showing the prompt.

Crucially: these hooks **explicitly write** to `$DEVTRACE_FIFO` using `printf >>"$DEVTRACE_FIFO"` – that’s how events enter the FIFO.

---

## 2. Two separate “pipes” to keep straight

### A. The interactive pipe: PTY₀ + PTY₁

This is what you see as “the terminal”:

* Your keystrokes go:

  ```text
  Keyboard → iTerm → PTY₀ master → PTY₀ slave → DevTrace stdin → PTY₁ master → PTY₁ slave → child shell
  ```
* Program output goes back in the reverse direction:

  ```text
  child shell → PTY₁ slave → PTY₁ master → DevTrace stdout (PTY₀ slave) → PTY₀ master → iTerm → Screen
  ```

This is all handled by:

* iTerm (outer terminal emulator) for PTY₀
* Python `pty.spawn` for PTY₁

**PTYS here only carry raw bytes** (prompts, commands, ls output, etc.) – they know nothing about “commands”, “exit codes”, etc.

### B. The logging pipe: FIFO (`/tmp/devtrace_cmd_<pid>`)

This is a **completely separate path** for structured metadata:

* The child shell hooks run around each command and do:

  ```bash
  printf 'CMD <epoch> <command>\n' >>"$DEVTRACE_FIFO"
  printf 'EXIT <epoch> <exit_code> <duration_ms> <cwd>\n' >>"$DEVTRACE_FIFO"
  ```
* The kernel puts those bytes into the FIFO’s buffer.
* DevTrace’s FIFO reader thread (in Python) is blocked on `read()` and wakes up when those lines arrive.

So you get a sequence like:

```text
CMD  1732400000 ls -la
EXIT 1732400002 0 2000 /home/you
CMD  1732400003 git status
EXIT 1732400004 1 1000 /home/you/project
...
```

DevTrace then parses these into proper events (`{command, timestamp, exit_code, duration, cwd}`) and stores them wherever it wants (log file, DB, API, etc.). The FIFO itself is just the **transport**.

---

## 3. One full command, step-by-step

Let’s simulate you typing `ls -la` in the DevTrace shell.

### 3.1 You type the command

1. You type `ls -la` + Enter in iTerm.
2. iTerm writes those bytes to **PTY₀ master**.
3. The kernel delivers them to **PTY₀ slave**.
4. DevTrace’s stdin (fd 0) is attached to PTY₀ slave, so `pty.spawn` reads them.
5. `pty.spawn` writes them to **PTY₁ master**.
6. Kernel delivers them to **PTY₁ slave**.
7. Child shell’s stdin is PTY₁ slave → it sees `ls -la\n`.

### 3.2 Preexec hook fires (before the command runs)

Inside bash (child shell):

1. DEBUG trap calls `_devtrace_preexec`.
2. `_devtrace_preexec` constructs a line, e.g.:

   ```text
   CMD 1732400000 ls -la
   ```
3. It runs:

   ```bash
   printf 'CMD 1732400000 ls -la\n' >>"$DEVTRACE_FIFO"
   ```

   which at syscall level is:

   * `open("/tmp/devtrace_cmd_12345", O_WRONLY|O_APPEND)`
   * `write(fd, "CMD 1732400000 ls -la\n")`
   * `close(fd)`
4. The kernel pushes that line into the FIFO’s in-kernel queue.

Meanwhile, DevTrace’s FIFO reader:

```python
with open("/tmp/devtrace_cmd_12345", "r") as f:
    for line in f:
        # blocks until line is written
```

* It was blocked in `read()`.
* The moment the hook writes, `read()` returns `"CMD 1732400000 ls -la\n"`.
* DevTrace now knows: **“User is about to run `ls -la` at timestamp X.”**

### 3.3 `ls -la` actually runs (interactive output)

* Bash executes `ls -la`:

  * `ls` writes its output to stdout → PTY₁ slave
  * Kernel passes that to PTY₁ master → DevTrace → PTY₀ slave → PTY₀ master → iTerm → your screen.
* None of this goes into the FIFO. It’s just normal terminal output through the PTYs.

### 3.4 Precmd hook fires (after the command finishes)

Once `ls` exits:

1. Bash is about to show the next prompt.
2. `PROMPT_COMMAND` runs `_devtrace_precmd`.
3. `_devtrace_precmd` sees:

   * `$?` → exit code (say `0`)
   * `$PWD` → `/home/you`
   * `SECONDS` + `_DEVTRACE_CMD_START` → `duration_ms`
4. It builds a line:

   ```text
   EXIT 1732400002 0 2000 /home/you
   ```
5. Runs:

   ```bash
   printf 'EXIT 1732400002 0 2000 /home/you\n' >>"$DEVTRACE_FIFO"
   ```
6. The kernel again enqueues this line into the FIFO buffer.

DevTrace’s FIFO reader, still in its `for line in f` loop, sees:

* First line: `CMD 1732400000 ls -la`
* Next line: `EXIT 1732400002 0 2000 /home/you`

It pairs them and builds a “run_command” event:

```python
event = {
    "command": "ls -la",
    "timestamp": 1732400000,
    "exit_code": 0,
    "duration_ms": 2000,
    "cwd": "/home/you",
}
```

Then it can log this, store it, etc.

---

## 4. Roles summarized in one shot

### PTY₀ (outer PTY – iTerm’s terminal)

* **Owner:** iTerm
* **Purpose:** Connects your keyboard/screen to your login shell (and to DevTrace when you run it).
* **DevTrace’s view:** Its stdin/stdout are attached to PTY₀ slave.

### PTY₁ (inner PTY – DevTrace’s terminal for child shell)

* **Owner:** DevTrace (`pty.spawn`)
* **Purpose:** Provide a real terminal environment for the child shell DevTrace launches, so it behaves just like a normal interactive shell (prompts, Ctrl-C, vim, etc.).
* **DevTrace’s job:** Copy bytes between PTY₁ master and PTY₀ slave.

### Hooks (bash/zsh)

* **Location:** Inside the **child shell** on PTY₁ slave.
* **Purpose:** Get *semantic* information (command text, exit code, timing, cwd) at the right times:

  * `preexec` (or DEBUG trap) → before command
  * `precmd` / PROMPT_COMMAND → after command
* **Action:** `printf 'CMD ...' >>"$DEVTRACE_FIFO"` and `printf 'EXIT ...' >>"$DEVTRACE_FIFO"`.

### FIFO (`/tmp/devtrace_cmd_<pid>`)

* **Type:** Named pipe (FIFO special file, created by `mkfifo`).
* **Purpose:** A **staging / transport channel** for structured CMD/EXIT lines from shell hooks to DevTrace.
* **Behavior:**

  * Writers (hooks) push bytes into it via `write()`.
  * Reader (DevTrace) pulls bytes out via `read()` in order.
  * Data is not persisted; once read, it’s gone.

### DevTrace Python process

* **Responsibilities:**

  1. **Create FIFO** and export its path via `DEVTRACE_FIFO`.
  2. **Start FIFO reader** thread: `for line in open(DEVTRACE_FIFO)`.
  3. **Spawn child shell inside a PTY** via `pty.spawn(...)` so the shell is fully interactive.
  4. **Parse CMD/EXIT lines** from FIFO into structured events.
  5. **Store / forward** those events (log file, DB, API, etc.).

So in one diagram:

```text
(Interactive channel)
YOU
  ↕
iTerm (outer terminal)
  ↕
PTY₀ master ↔ PTY₀ slave ↔ DevTrace (Python, pty.spawn)
                             ↕
                        PTY₁ master ↔ PTY₁ slave ↔ Child shell (hooks)

(Logging channel)
Child shell hooks
   ↘  printf CMD/EXIT >> $DEVTRACE_FIFO
    FIFO (/tmp/devtrace_cmd_<pid>)
      ↘
      DevTrace fifo_reader → parse → store/use events
```

If you want, we can next:

* Turn this into a **README diagram** (ASCII or Mermaid) you can drop straight into your DevTrace repo, or
* Sketch Option A (pure hooks+FIFO, no PTY wrapper) vs Option B (full DevTrace shell) as two “modes” for your future project.
