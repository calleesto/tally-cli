import os
import select
import shutil
import signal
import sys
import termios
import tty

from tally.storage import format_amount, parse_amount

# Black background, phosphor green foreground.
SCREEN = "\033[40;92m"
DIM = "\033[32m"
BRIGHT = "\033[92m"
SELECT = "\033[30;102m"


class ExitApp(Exception):
    """Raised when the user leaves the session from the keyboard."""


class Terminal:
    """Full-screen input. Each key redraws a cleared screen."""

    def __init__(self):
        self.notice = ""
        self.fd = None
        self.original = None
        self.active = False
        self.pending = b""

    def enter(self):
        self.fd = sys.stdin.fileno()
        if self.original is None:
            self.original = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        sys.stdout.write("\033[?1049h\033[?25l" + SCREEN)
        sys.stdout.flush()
        self.active = True

    def leave(self):
        if not self.active and self.original is None:
            return
        sys.stdout.write("\033[0m\033[?25h\033[?1049l")
        sys.stdout.flush()
        if self.original is not None and self.fd is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original)
        self.active = False

    def install_signals(self):
        def on_stop(signum, frame):
            self.leave()
            signal.signal(signal.SIGTSTP, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGTSTP)

        def on_cont(signum, frame):
            self.enter()
            signal.signal(signal.SIGTSTP, on_stop)

        signal.signal(signal.SIGTSTP, on_stop)
        signal.signal(signal.SIGCONT, on_cont)

    def render(self, lines):
        sys.stdout.write("\033[2J\033[H" + SCREEN + "\n".join(lines) + "\n" + SCREEN)
        sys.stdout.flush()

    def read_key(self):
        chunk = self._read_byte()
        if chunk in (b"", b"\x03", b"\x04"):
            raise ExitApp
        if chunk == b"\x1b":
            return self._read_escape()
        if chunk in (b"\r", b"\n"):
            return "enter"
        if chunk in (b"\x7f", b"\x08"):
            return "backspace"
        if chunk[0] >= 128:
            length = 2 if chunk[0] < 224 else 3 if chunk[0] < 240 else 4
            while len(chunk) < length:
                chunk += self._read_byte()
            return chunk.decode("utf-8", "replace")
        return chunk.decode("ascii", "replace")

    def _read_byte(self, timeout=None):
        if self.pending:
            byte = self.pending[:1]
            self.pending = self.pending[1:]
            return byte
        if timeout is not None and not select.select([self.fd], [], [], timeout)[0]:
            return b""
        return os.read(self.fd, 1)

    def _read_escape(self):
        second = self._read_byte(0.03)
        if second not in (b"[", b"O"):
            if second:
                self.pending = second + self.pending
            return "esc"
        third = self._read_byte(0.03)
        if not third:
            return "esc"
        sequence = b"\x1b" + second + third
        if third.isdigit() or third in b";?":
            while True:
                nxt = self._read_byte(0.03)
                if not nxt:
                    break
                sequence += nxt
                if nxt.isalpha() or nxt == b"~":
                    break
        if sequence in (b"\x1b[A", b"\x1bOA"):
            return "up"
        if sequence in (b"\x1b[B", b"\x1bOB"):
            return "down"
        if sequence in (b"\x1b[D", b"\x1bOD"):
            return "left"
        if sequence in (b"\x1b[C", b"\x1bOC"):
            return "right"
        return "esc"

    def menu(self, header, options, allow_escape=True, screen=None):
        index = 0
        while True:
            lines = banner(screen)
            lines.extend(header)
            lines.append("")
            lines.append(heading("Actions"))
            lines.append("")
            for option_index, option in enumerate(options):
                lines.append(self._item(option, option_index == index))
            lines.append("")
            if screen:
                hint = "↑ ↓ move     ← → switch     Enter select"
            else:
                hint = "↑ ↓ move     Enter select"
            lines.append(f"{DIM}{hint}{BRIGHT}")
            self._append_notice(lines)
            self.render(lines)
            key = self.read_key()
            self.notice = ""
            if key == "up":
                index = (index - 1) % len(options)
            elif key == "down":
                index = (index + 1) % len(options)
            elif key == "enter":
                return index
            elif key in ("left", "right") and screen:
                return key
            elif key == "esc" and allow_escape:
                return None

    def edit(self, header, label, initial="", error="", allow_escape=True):
        value = initial
        while True:
            lines = banner()
            lines.extend(header)
            lines.append("")
            lines.append(f"{DIM}{label}{BRIGHT}")
            lines.append(value + "█")
            lines.append("")
            hint = "Enter confirm"
            if allow_escape:
                hint += "     Esc cancel"
            lines.append(f"{DIM}{hint}{BRIGHT}")
            if error:
                lines.append("")
                lines.append(error)
            self._append_notice(lines)
            self.render(lines)
            key = self.read_key()
            self.notice = ""
            if key == "enter":
                return value.strip()
            if key == "esc" and allow_escape:
                return None
            if key == "backspace":
                value = value[:-1]
                error = ""
            elif len(key) == 1 and key.isprintable():
                value += key
                error = ""

    def _append_notice(self, lines):
        if self.notice:
            lines.append("")
            lines.append(self.notice)

    @staticmethod
    def _item(label, selected):
        text = f"  {label}  "
        if selected:
            return f"{SELECT}{text}{SCREEN}"
        return text


def ask_text(ui, header, label, allow_empty=False, allow_escape=True):
    error = ""
    initial = ""
    while True:
        value = ui.edit(header, label, initial, error, allow_escape=allow_escape)
        if value is None:
            return None
        initial = value
        if value or allow_empty:
            return value
        error = "This field cannot be empty."


def ask_amount(ui, header, label, allow_zero=True, allow_escape=True):
    error = ""
    initial = ""
    while True:
        raw = ui.edit(header, label, initial, error, allow_escape=allow_escape)
        if raw is None:
            return None
        initial = raw
        amount, error = parse_amount(raw, allow_zero=allow_zero)
        if error is None:
            return amount


def screen_width():
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(40, min(columns - 2, 78))


def banner(screen=None):
    lines = ["Tally", f"{DIM}{'─' * screen_width()}{BRIGHT}"]
    tabs = (("budget", "Budget"), ("categories", "Categories"), ("insights", "Insights"))
    if screen in {key for key, _label in tabs}:
        parts = []
        for key, label in tabs:
            if key == screen:
                parts.append(label)
            else:
                parts.append(f"{DIM}{label}{BRIGHT}")
        lines.append("      ".join(parts))
    lines.append("")
    return lines


def heading(text):
    return f"{DIM}{text}{BRIGHT}"


def meter(remaining, total, width=20):
    """Full when nothing has been spent, and shorter after each expense."""
    if total <= 0:
        return f"{DIM}{'░' * width}{BRIGHT}    --"
    ratio = remaining / total
    if ratio >= 1:
        filled = width
    elif ratio <= 0:
        filled = 0
    else:
        filled = int(round(ratio * width))
        filled = min(width - 1, max(1, filled))
    percent = int(round(max(0.0, min(1.0, ratio)) * 100))
    return (
        f"{BRIGHT}{'█' * filled}"
        f"{DIM}{'░' * (width - filled)}"
        f"{BRIGHT}  {percent:>3}% left"
    )


def money_row(pairs):
    cells = [f"{label:<12}{format_amount(value):>10}" for label, value in pairs]
    return "  " + "    ".join(cells)


def bar_width():
    return max(12, min(24, screen_width() - 16))
