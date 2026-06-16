"""Color-coded terminal output for VoiceOS (CLI-only interface)."""

from __future__ import annotations

import sys
from typing import Optional

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
    _COLORS = True
except ImportError:
    _COLORS = False

    class _NoColor:
        def __getattr__(self, _):
            return ""

    Fore = Style = _NoColor()  # type: ignore


class VoiceConsole:
    """Structured, color-coded CLI output for PowerShell, cmd, and Unix terminals."""

    PROMPT = f"{Fore.GREEN}VoiceOS{Style.RESET_ALL}{Fore.CYAN}>{Style.RESET_ALL} "

    @classmethod
    def enabled(cls) -> bool:
        return _COLORS and sys.stdout.isatty()

    @classmethod
    def _print(cls, prefix: str, color: str, message: str, bold: bool = False) -> None:
        if not cls.enabled():
            print(f"{prefix} {message}")
            return
        weight = Style.BRIGHT if bold else ""
        print(f"{weight}{color}{prefix}{Style.RESET_ALL} {message}")

    @classmethod
    def banner(cls) -> None:
        line = "=" * 58
        if cls.enabled():
            print(f"{Fore.CYAN}{Style.BRIGHT}{line}")
            print("  VoiceOS - CLI Multi-Agent Operating System")
            print("  Voice + terminal control - no GUI required")
            print(f"{line}{Style.RESET_ALL}")
        else:
            print(line)
            print("  VoiceOS — CLI Multi-Agent Operating System")
            print(line)

    @classmethod
    def info(cls, message: str) -> None:
        cls._print("[info]", Fore.CYAN, message)

    @classmethod
    def success(cls, message: str) -> None:
        cls._print("[ok]", Fore.GREEN, message, bold=True)

    @classmethod
    def warning(cls, message: str) -> None:
        cls._print("[warn]", Fore.YELLOW, message)

    @classmethod
    def error(cls, message: str) -> None:
        cls._print("[error]", Fore.RED, message, bold=True)

    @classmethod
    def flow(cls, stage: str, detail: str = "") -> None:
        text = f"{stage}: {detail}" if detail else stage
        cls._print("[flow]", Fore.MAGENTA, text)

    @classmethod
    def agent(cls, role: str, message: str) -> None:
        cls._print(f"[agent:{role}]", Fore.BLUE, message)

    @classmethod
    def tool(cls, name: str, message: str = "") -> None:
        detail = f" — {message}" if message else ""
        cls._print("[tool]", Fore.YELLOW, f"{name}{detail}")

    @classmethod
    def permission(cls, message: str) -> None:
        cls._print("[permission]", Fore.RED, message, bold=True)

    @classmethod
    def response(cls, text: str) -> None:
        if cls.enabled():
            print(f"{Fore.GREEN}{Style.BRIGHT}VoiceOS:{Style.RESET_ALL} {text}")
        else:
            print(f"VoiceOS: {text}")

    @classmethod
    def voice(cls, text: str) -> None:
        cls._print("[voice]", Fore.CYAN, text)

    @classmethod
    def dim(cls, message: str) -> None:
        if cls.enabled():
            print(f"{Style.DIM}{message}{Style.RESET_ALL}")
        else:
            print(message)

    @classmethod
    def section(cls, title: str) -> None:
        if cls.enabled():
            print(f"\n{Fore.CYAN}{Style.BRIGHT}── {title} ──{Style.RESET_ALL}")
        else:
            print(f"\n── {title} ──")

    @classmethod
    def prompt(cls, text: Optional[str] = None) -> str:
        return input(text or cls.PROMPT)
