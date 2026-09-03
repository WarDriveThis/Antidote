# uart_sync.py — Antidote Pi → ESP32-S3 identifier sync over UART
#
# Option A IPC: Pi is the source of truth.
# On a configurable interval, this module selects a random sample from the
# identifier pool and pushes it to the ESP32-S3 as newline-delimited JSON.
#
# Protocol (Pi → ESP32-S3):
#   One JSON object per line, ending with \n.
#   Format: {"ids": [{"cat": "ble_mac", "value": "AA:BB:CC:DD:EE:FF"}, ...]}
#
# The ESP32-S3 replaces its local exhale buffer with the received sample.
# No acknowledgment is expected — the protocol is intentionally one-directional
# and lossy. If a push is missed, the ESP32 uses its previous buffer.
#
# Failure behaviour:
#   If the serial port is unavailable, a warning is logged and the sync
#   is skipped. The next attempt will be made after uart_sync_interval seconds.
#   This means the UART cable can be unplugged and re-plugged without
#   restarting Antidote.

import serial
import json
import time
import threading


class UartSync:
    def __init__(self, pool, config, logger):
        self.pool  = pool
        self.cfg   = config
        self.log   = logger
        self._port = None
        self._lock = threading.Lock()
        self._running = False
        self._thread  = None
        self._last_push_time = 0
        self._push_count = 0
        self._last_error = None

    def _open_port(self) -> bool:
        port = self.cfg.get("uart_port", "/dev/serial0")
        baud = self.cfg.get("uart_baud", 115200)
        try:
            self._port = serial.Serial(
                port      = port,
                baudrate  = baud,
                timeout   = 1.0,
                write_timeout = 2.0,
            )
            self.log.info(f"[UART] Opened {port} at {baud} baud.")
            return True
        except serial.SerialException as e:
            self.log.warn(f"[UART] Cannot open {port}: {e}")
            self._last_error = str(e)
            self._port = None
            return False

    def _close_port(self):
        if self._port and self._port.is_open:
            try:
                self._port.close()
            except Exception:
                pass
        self._port = None

    def push_sample(self) -> bool:
        """
        Select a random sample from the pool and send it to the ESP32-S3.
        Returns True if the push succeeded.
        """
        n = self.cfg.get("uart_sample_size", 50)

        # Prefer BLE identifiers for exhale (ESP32 is BLE-only exhale device)
        # v1.1: includes manufacturer specific data category
        ble_cats = [
            self.pool.CAT_BLE_MAC,
            self.pool.CAT_BLE_UUID,
            self.pool.CAT_BLE_NAME,
            self.pool.CAT_BLE_MANUF,
        ]
        sample = self.pool.get_random_sample(n=n, categories=ble_cats)

        # Fall back to all categories if BLE pool is thin
        if len(sample) < 5:
            sample = self.pool.get_random_sample(n=n)

        if not sample:
            self.log.debug("[UART] Pool empty, skipping sync push.")
            return False

        payload = json.dumps({"ids": sample}) + "\n"

        with self._lock:
            # Try to open the port if it's not open
            if not self._port or not self._port.is_open:
                if not self._open_port():
                    return False

            try:
                self._port.write(payload.encode("utf-8"))
                self._port.flush()
                self._last_push_time = time.time()
                self._push_count    += 1
                self._last_error     = None
                self.log.debug(f"[UART] Pushed {len(sample)} identifiers to ESP32-S3.")
                return True

            except serial.SerialException as e:
                self.log.warn(f"[UART] Send error: {e} — will retry on next cycle.")
                self._last_error = str(e)
                self._close_port()   # Force re-open on next attempt
                return False

    def start(self):
        """Start background sync loop."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name="uart-sync")
        self._thread.start()
        self.log.info("[UART] Sync loop started.")

    def stop(self):
        self._running = False
        self._close_port()

    def _loop(self):
        while self._running:
            interval = self.cfg.get("uart_sync_interval", 30)
            time.sleep(interval)
            if self._running:
                self.push_sample()

    def status(self) -> dict:
        return {
            "port":         self.cfg.get("uart_port"),
            "connected":    bool(self._port and self._port.is_open),
            "push_count":   self._push_count,
            "last_push":    self._last_push_time,
            "last_error":   self._last_error,
        }
