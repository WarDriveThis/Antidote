# uart_receive.py - Receive identifier pushes from Raspberry Pi
#
# Runs on Thread 1. Listens on UART1 for JSON lines from the Pi.
# Protocol: {"ids": [{"cat": "...", "value": "..."}, ...]}
#
# Pin assignments (XIAO ESP32-S3) — verified working:
#   ESP RX = D6 = GPIO43  <- Pi Pin 10 (GPIO15 RX, but wired to Pi TX)
#   ESP TX = D7 = GPIO44  -> Pi Pin 8  (GPIO14 TX, but wired to Pi RX)
#
# Physical wiring:
#   ESP D6 (GPIO43) -> Pi Pin 10
#   ESP D7 (GPIO44) -> Pi Pin 8
#   ESP GND         -> Pi Pin 6

import machine
import json
import time

UART_BAUD = 115200
UART_RX   = 43   # D6 <- Pi Pin 10
UART_TX   = 44   # D7 -> Pi Pin 8


class UartReceive:
    def __init__(self, pool, config, logger, hardware):
        self.pool = pool
        self.cfg  = config
        self.log  = logger
        self.hw   = hardware
        self._uart = None
        self._rx_count = 0

    def _init_uart(self):
        try:
            self._uart = machine.UART(1,
                baudrate = UART_BAUD,
                tx       = UART_TX,
                rx       = UART_RX,
                timeout  = 100,
            )
            self.log.info("[UART-RX] Opened UART1 RX=GPIO{} TX=GPIO{} at {}".format(
                UART_RX, UART_TX, UART_BAUD))
            return True
        except Exception as e:
            self.log.error("[UART-RX] Init failed: {}".format(e))
            return False

    def _process_line(self, line):
        line = line.strip()
        if len(line) < 10:
            return 0
        try:
            msg  = json.loads(line)
            ids  = msg.get("ids", [])
            count = 0
            for entry in ids:
                cat   = entry.get("cat")
                value = entry.get("value")
                if cat and value:
                    self.pool.add(cat, value)
                    count += 1
            if count > 0:
                self._rx_count += count
                self.log.info("[UART-RX] Received {} IDs from Pi. Pool={}".format(
                    count, self.pool.count()))
                self._green_flash()
            return count
        except Exception as e:
            self.log.error("[UART-RX] Parse error: {}".format(e))
            return 0

    def _green_flash(self):
        try:
            self.hw.stop_pulse()
            time.sleep_ms(60)
            for _ in range(3):
                self.hw.set_color(self.hw.COLOR_GREEN)
                time.sleep_ms(100)
                self.hw.set_color(self.hw.COLOR_OFF)
                time.sleep_ms(100)
            self.hw.pulse(self.hw.COLOR_WHITE)
        except Exception:
            pass

    def run(self):
        if not self._init_uart():
            return
        buf = b""
        # Flush any partial data already in buffer
        time.sleep_ms(200)
        if self._uart.any():
            self._uart.read(self._uart.any())
        while True:
            try:
                if self._uart.any():
                    chunk = self._uart.read(self._uart.any())
                    if chunk:
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            try:
                                self._process_line(line.decode("utf-8", "ignore"))
                            except Exception as e:
                                self.log.error("[UART-RX] Line err: {}".format(e))
                else:
                    time.sleep_ms(50)
            except Exception as e:
                self.log.error("[UART-RX] Loop error: {}".format(e))
                time.sleep_ms(500)
