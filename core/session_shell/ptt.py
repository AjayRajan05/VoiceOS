"""Optional push-to-talk key listener."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_KEY_ALIASES = {
    "space": "space",
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
}


class PushToTalkListener:
    """Hold a key to enable voice capture (push-to-talk mode)."""

    def __init__(self, key: str = "space", on_change: Optional[Callable[[bool], None]] = None):
        self.key = _KEY_ALIASES.get(key.lower().strip(), key.lower().strip())
        self.on_change = on_change
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="voiceos-ptt", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._active:
            self._set_active(False)

    def _run(self) -> None:
        try:
            from pynput import keyboard
        except ImportError:
            logger.warning("pynput not available; push-to-talk disabled")
            return

        pressed = {False}

        def on_press(key):
            if not self._running:
                return False
            if self._key_matches(key) and not pressed[0]:
                pressed[0] = True
                self._set_active(True)

        def on_release(key):
            if self._key_matches(key) and pressed[0]:
                pressed[0] = False
                self._set_active(False)

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            while self._running:
                listener.join(timeout=0.2)
                if not listener.running:
                    break

    def _key_matches(self, key) -> bool:
        from pynput import keyboard

        if self.key == "space":
            return key == keyboard.Key.space
        if self.key == "ctrl":
            return key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)
        if self.key == "shift":
            return key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r)
        if self.key == "alt":
            return key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r)
        try:
            char = getattr(key, "char", None)
            return char is not None and char.lower() == self.key
        except Exception:
            return False

    def _set_active(self, active: bool) -> None:
        self._active = active
        if self.on_change:
            try:
                self.on_change(active)
            except Exception as exc:
                logger.debug("PTT callback error: %s", exc)
