"""Tests for per-thread interrupt signaling."""

import threading
import time

from interrupt.thread_interrupt import clear_interrupt, is_interrupted, set_interrupt


def test_interrupt_is_thread_scoped():
    clear_interrupt()

    def worker():
        set_interrupt(True)
        assert is_interrupted() is True

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert is_interrupted() is False


def test_clear_interrupt():
    set_interrupt(True)
    assert is_interrupted() is True
    clear_interrupt()
    assert is_interrupted() is False
