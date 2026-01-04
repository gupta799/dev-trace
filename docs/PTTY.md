Here’s a README-style explanation you can drop straight into a repo.

---

# Understanding PTYs, TTYs, and Shells (bash, zsh, etc.)

This document explains **what a PTY is**, how it relates to **TTYs**, and how tools like **iTerm2 / GNOME Terminal / SSH / tmux** use them. It’s written from the point of view of a developer new to these concepts.

---

## 1. Big picture: who’s who?

There are four main actors:

* **You** – human at the keyboard
* **Shell** – e.g. `bash`, `zsh`, `fish` (just normal programs)
* **Terminal / terminal emulator** – e.g. iTerm2, GNOME Terminal, `xterm`, or `sshd`, `tmux`
* **Kernel device** – TTY or PTY

Core idea:

> A **TTY/PTY is *not* a shell.**
> It’s a **device** (or virtual device) the shell uses to get input and send output.

The shell:

* **Reads commands** from **stdin**.
* **Prints prompts/output** to **stdout/stderr**.

What stdin/stdout are *hooked up to* decides whether the shell is “in a terminal” (interactive) or just reading from a file/pipe.

---

## 2. TTY vs PTY (real vs virtual terminals)

### 2.1 TTY: “real” terminal devices

Historically, a **TTY** was a teletype machine; in modern Unix, it means **any device that behaves like a text terminal**. Examples:

* Kernel virtual consoles like `/dev/tty1`, `/dev/tty2` (the `Ctrl+Alt+F3` style consoles on Linux).
* Serial ports like `/dev/ttyS0` on older systems.

These devices support the “terminal interface”: line discipline, control characters (`Ctrl+C`, `Ctrl+Z`), echo, etc.

### 2.2 PTY: pseudo-terminal pair (master + slave)

A **pseudoterminal (PTY)** is a **pair of virtual character devices** that together behave like a terminal: one end is the **master**, the other is the **slave**.

* **Slave**:

  * Looks to programs just like a normal TTY (e.g. `/dev/pts/0`).
  * A shell, `vim`, `top`, etc. attach their stdin/stdout to this.
* **Master**:

  * Used by a **controlling program** (terminal emulator, SSH server, `tmux`, etc.).
  * Anything written to master appears as input on slave; anything written to slave can be read from master.

This is the standard description in `man 7 pty` and related docs.

### 2.3 Why “pseudo”?

Because there’s no physical terminal behind it. The slave **emulates** a hardware terminal; the master side is driven by another process instead of a real keyboard/screen.

---

## 3. File descriptors and stdin/stdout (how shells see the world)

Every Unix process starts with three “standard” **file descriptors**:

* **0** → stdin (standard input)
* **1** → stdout (standard output)
* **2** → stderr (standard error)

A “file descriptor” is just a small integer pointing to some open I/O object: a file, a pipe, a socket, a terminal, or a PTY.

For a shell (`bash`):

* It **reads commands** from FD **0**.
* It **prints output** to FD **1**/**2**.
* It can ask: “Is FD 0 a terminal?” using `isatty(0)` or equivalent.

The environment you put around bash is just: **what do 0/1/2 point to?**

### 3.1 Example: interactive shell (PTY)

In a terminal window:

```bash
$ tty
/dev/pts/0
```

* `bash`’s stdin/stdout point to `/dev/pts/0` (PTY **slave**).
* `isatty(0)` is true → bash is interactive (prompts, line editing, job control, etc.).

### 3.2 Example: shell from a pipe (non-interactive)

```bash
echo 'echo hi' | bash
```

Under the hood, the shell creates a **pipe**, connects:

* `echo`’s stdout → pipe write end
* `bash`’s stdin → pipe read end

For `bash`:

* stdin (FD 0) now points to a **pipe**, not a TTY/PTY.
* `isatty(0)` is false → bash treats itself as **non-interactive**, reads until EOF, runs commands, exits.

Same program, different behavior, just because stdin/stdout are connected to a **different kind of device**.

---

## 4. How a PTY is used in practice

### 4.1 Terminal emulators (iTerm2, GNOME Terminal, Alacritty, etc.)

When you open iTerm2:

1. It asks the kernel for a PTY pair (e.g. by opening `/dev/ptmx`, which creates a new master + `/dev/pts/N` slave).
2. It forks a child process, sets that child’s stdin/stdout/stderr to the **slave** (`/dev/pts/N`), and execs your shell (`bash`, `zsh`, etc.).
3. iTerm2 keeps the **master** FD and runs an event loop:

   * Reads bytes from master, parses escape sequences (colors, cursor movement) and draws them in the window.
   * Converts your key presses/mouse actions into bytes and writes them to master.

From the shell’s point of view:

> “I’m on a normal terminal device `/dev/pts/N`.”

From iTerm’s point of view:

> “I see all bytes going in and out and can provide scrollback, fonts, colors, tabs, logging, etc.”

This is exactly the architecture described in many PTY tutorials and articles on terminal emulators.

---

### 4.2 SSH with and without a PTY

Normal SSH:

```bash
ssh user@server
```

On the **remote** side, `sshd` usually:

* Allocates a PTY pair.
* Gives the **slave** to your login shell (`/dev/pts/N`).
* Keeps the **master** to send your keystrokes and read the shell’s output over the network.

Then, on the remote:

```bash
$ tty
/dev/pts/1
```

Now compare:

```bash
ssh -T user@server "python3"
```

* `-T` = **do not allocate a TTY**.
* `python3`’s stdin/stdout become **pipes**, not a PTY.
* If you run `tty` in that command, it prints something like `not a tty`, because stdin is not a terminal device. (This is consistent with how SSH’s `-T` is documented: no PTY, plain stdio only.)

Why this matters:

* With a PTY, programs behave **interactively** (`python` REPL, `top`, `vim`, etc.).
* Without a PTY, they behave like they’re in a non-interactive script or batch mode.

---

### 4.3 `tmux` / `screen`

Tools like **tmux** and **screen** also sit on the **master** side of a PTY, and then create more PTYs internally:

* Your GUI terminal:

  * Holds `master₁`, runs `tmux` with stdin/stdout on `slave₁`.
* `tmux`:

  * Allocates `master₂/slave₂` for each pane.
  * Runs `bash` in each pane with stdin/stdout on `slave₂`.

Chain:

```text
you → GUI terminal (master₁) → slave₁ (tmux) → master₂ → slave₂ (bash)
```

Each layer is “a program that controls a PTY master and provides a terminal to something on the slave”.

---

### 4.4 Docker / Kubernetes: the `-t` flag

When you run:

```bash
docker run -it ubuntu bash
```

* `-i` = keep stdin open.
* `-t` = ask Docker to allocate a TTY (implemented via a PTY on the host).

Inside the container:

```bash
tty
# /dev/pts/0 (or similar)
```

If you omit `-t`, many interactive programs will not work or will behave differently, because they don’t see a TTY/PTY.

---

## 5. Why PTYs instead of just pipes?

Pipes give you “just bytes”. PTYs give you **terminal semantics**.

### 5.1 PTYs support the terminal interface

The PTY **slave** implements the same interface as a classical terminal device:

* Line discipline (canonical vs raw mode)
* Special control characters (`Ctrl+C`, `Ctrl+Z`, `Ctrl+D`, backspace, etc.)
* Session and foreground process group tracking
* Window size changes (`SIGWINCH`)

That’s why docs say: the slave “provides an interface that behaves exactly like a classical terminal”; the master is how another process drives it.

If we only used pipes:

* `isatty()` would be false.
* Shells and tools would disable interactive features.
* Job control and signal handling wouldn’t work the same way.
* Full-screen TUIs (vim, top, htop, etc.) wouldn’t behave correctly.

### 5.2 PTYs let another program “pretend to be the keyboard + screen”

The master side is essential because it is **where the terminal emulator / sshd / tmux connects**:

* It **injects input** (your keystrokes, mouse events) by writing to master.
* It **reads output** (everything the app writes) by reading from master.
* It parses control sequences, maintains scrollback, draws fonts, etc.

Without the master, there’d be no way for a separate user-facing program to sit in between the kernel’s terminal driver and your shell.

---

## 6. Minimal mental model

If you remember nothing else:

* A **TTY** is a “real-ish” terminal device (hardware or kernel virtual).
* A **PTY** is a **virtual terminal pair**:

  * **Slave** = looks like a real terminal to programs.
  * **Master** = controlled by a program (terminal emulator, sshd, tmux) that:

    * reads everything the program prints,
    * writes everything the user types.
* **Shells (bash, zsh, python REPL, etc.) are just programs** whose stdin/stdout may be connected to:

  * a TTY/PTY slave → interactive terminal
  * a pipe/file → non-interactive batch/script mode.

---

## 7. Quick command cheatsheet

Try these on a Linux/macOS system:

```bash
# See which terminal device your shell is attached to
tty

# Check if stdin is a terminal (Python)
python3 -c "import sys; print(sys.stdin.isatty())"

# Run bash in non-interactive mode (stdin from a pipe)
echo 'echo hi' | bash

# Remote command with a PTY
ssh -t user@server 'tty'

# Remote command without a PTY
ssh -T user@server 'tty'   # often prints "not a tty"
```

These small experiments make the abstract ideas very concrete.

---

## 8. Further reading

If you want to go deeper, these are excellent references:

* **Linux man pages**

  * `man 7 pty` – pseudoterminal overview
  * `man 4 pts` – PTY devices
  * `man 3 openpty` – convenience function for creating PTYs
* **Wikipedia – Pseudoterminal** – good high-level description and history.
* **Blog posts / tutorials**

  * *“The very basics of a terminal emulator”* – walking through building a minimal emulator.
  * *“Linux terminals, tty, pty and shell”* – clear high-level explanation of how terminal emulators use PTYs.

---

If you’d like, I can add a section with **ASCII diagrams** and/or **pseudo-code** for a “toy terminal emulator” that:

1. calls `openpty()`
2. forks a child to run `/bin/bash` on the slave
3. runs a loop copying between the PTY master and your stdin/stdout.
