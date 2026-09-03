# logger.py — Antidote Pi ring-buffer logger
import time
import threading


class Logger:
    def __init__(self, max_entries: int = 200):
        self._entries = []
        self._max     = max_entries
        self._lock    = threading.Lock()

    def _log(self, level: str, msg: str):
        ts    = time.strftime("%H:%M:%S")
        entry = f"[{ts}] [{level:4s}] {msg}"
        print(entry, flush=True)
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries.pop(0)

    def info(self, msg):  self._log("INFO", msg)
    def warn(self, msg):  self._log("WARN", msg)
    def error(self, msg): self._log("ERR ", msg)
    def debug(self, msg): self._log("DBG ", msg)

    def recent(self, n: int = 50) -> list:
        with self._lock:
            return list(self._entries[-n:])
