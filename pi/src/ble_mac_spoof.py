# ble_mac_spoof.py — Antidote Pi BLE MAC Spoofing Engine v1.5
#
# Uses Laird BL654 dongle (or any nRF52840 dongle flashed with Zephyr
# hci_usb firmware) connected via USB, enumerated as hci0 by BlueZ.
#
# Address spoofing mechanism:
#   HCI LE Set Random Address command (OGF=0x08, OCF=0x0005)
#   sent via hcitool while controller is powered and not advertising.
#   This sets the random address used in all subsequent LE advertisements.
#
# Confirmed working sequence:
#   1. Stop any active advertisement
#   2. Send LE Set Random Address HCI command with target MAC
#   3. Start LE advertisement via direct HCI commands (OCF 0x0006/0x0008/0x000A)
#   4. Wait interval, repeat with next MAC from pool
#
# Prerequisites:
#   - Dongle flashed with Zephyr hci_usb sample
#   - sudo rfkill unblock bluetooth (added to systemd service)
#   - sudo hciconfig hci0 up (added to systemd service)

import subprocess
import threading
import time
import random
import logging

log = logging.getLogger("ble_mac_spoof")


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def _hci_set_random_addr(hci_iface, mac):
    """
    Send HCI LE Set Random Address command directly.
    OGF=0x08, OCF=0x0005, plen=6 (MAC bytes in reverse order).
    Returns True on success (HCI status 0x00).
    """
    # Parse MAC and reverse byte order for HCI little-endian format
    try:
        parts = mac.upper().split(":")
        if len(parts) != 6:
            return False
        # HCI expects bytes in reverse order
        reversed_parts = list(reversed(parts))
        ok, out, err = _run([
            "hcitool", "-i", hci_iface, "cmd",
            "0x08", "0x0005"
        ] + reversed_parts, timeout=5)
        # Check for success status in response: "01 05 20 00" — last byte 0x00 = success
        return ok and "00" in out.split()[-1:] if out else ok
    except Exception as e:
        log.error(f"[BLE-SPOOF] HCI command error: {e}")
        return False


def _stop_advertising(hci_iface):
    """Disable LE advertising via direct HCI command (OGF=0x08 OCF=0x000A, enable=0x00)."""
    try:
        subprocess.run(
            ["hcitool", "-i", hci_iface, "cmd", "0x08", "0x000A", "0x00"],
            capture_output=True, timeout=3
        )
    except Exception:
        pass


def _start_advertising(hci_iface):
    """Enable non-connectable LE advertising via direct HCI commands.
    Sets adv params then enables. OGF=0x08.
    """
    try:
        # HCI LE Set Advertising Parameters (OCF=0x0006)
        # min_interval=0x00A0(100ms) max_interval=0x00A0 adv_type=0x03(non-conn)
        # own_addr_type=0x01(random) peer_addr_type=0 peer_addr=000000000000
        # channel_map=0x07(all) filter=0x00
        subprocess.run(
            ["hcitool", "-i", hci_iface, "cmd",
             "0x08", "0x0006",
             "A0", "00",   # min interval
             "A0", "00",   # max interval
             "03",          # adv type: non-connectable undirected
             "01",          # own addr type: random
             "00",          # peer addr type
             "00", "00", "00", "00", "00", "00",  # peer addr
             "07",          # channel map: all
             "00"],         # filter policy
            capture_output=True, timeout=3
        )
        # HCI LE Set Advertising Data (OCF=0x0008) — minimal flags AD
        # total_len=3, flags AD: len=2, type=0x01, value=0x06
        subprocess.run(
            ["hcitool", "-i", hci_iface, "cmd",
             "0x08", "0x0008",
             "03",                          # total significant bytes
             "02", "01", "06",          # flags: LE general discoverable, no BR/EDR
             # remaining 28 bytes padding
             "00","00","00","00","00","00","00",
             "00","00","00","00","00","00","00",
             "00","00","00","00","00","00","00",
             "00","00","00","00","00","00","00"],
            capture_output=True, timeout=3
        )
        # HCI LE Set Advertising Enable (OCF=0x000A, enable=0x01)
        r = subprocess.run(
            ["hcitool", "-i", hci_iface, "cmd", "0x08", "0x000A", "0x01"],
            capture_output=True, timeout=3
        )
        return r.returncode == 0
    except Exception:
        return False


def _check_hci(hci_iface):
    ok, out, _ = _run(["hciconfig", hci_iface])
    return ok and "UP RUNNING" in out


class BleMacSpoofer:
    def __init__(self, pool, config, logger):
        self.pool     = pool
        self.cfg      = config
        self.log      = logger
        self._thread  = None
        self._running = False
        self._current_mac = None
        self._cycle_count = 0

    def start(self):
        if not self.cfg.get("ble_mac_spoof_enabled", False):
            self.log.info("[BLE-SPOOF] Disabled in config.")
            return
        if not _check_hci(self._hci()):
            self.log.error(
                f"[BLE-SPOOF] {self._hci()} not UP RUNNING — "
                "is dongle connected and rfkill unblocked?"
            )
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._run_loop, daemon=True, name="ble-mac-spoof")
        self._thread.start()
        self.log.info(
            f"[BLE-SPOOF] MAC spoofing engine started on {self._hci()}. "
            f"Cycling every {self.cfg.get('ble_mac_spoof_interval', 30)}s."
        )

    def stop(self):
        self._running = False
        hci_iface = self._hci()
        _stop_advertising(hci_iface)
        self.log.info("[BLE-SPOOF] Stopped.")

    def _hci(self):
        return self.cfg.get("ble_mac_spoof_interface", "hci0")

    def _run_loop(self):
        hci_iface = self._hci()
        interval = self.cfg.get("ble_mac_spoof_interval", 30)

        while self._running:
            try:
                macs = self.pool.get_by_category(self.pool.CAT_BLE_MAC)
                if not macs:
                    self.log.debug("[BLE-SPOOF] No BLE MACs in pool yet, waiting...")
                    time.sleep(10)
                    continue

                mac = random.choice(macs)

                # Validate MAC format
                if len(mac) != 17 or mac.count(":") != 5:
                    time.sleep(interval)
                    continue

                # Stop current advertisement
                _stop_advertising(hci_iface)
                time.sleep(0.3)

                # Set new random address via HCI command
                if _hci_set_random_addr(self._hci(), mac):
                    # Start advertising with new address
                    if _start_advertising(hci_iface):
                        self._current_mac = mac
                        self._cycle_count += 1
                        self.log.info(
                            f"[BLE-SPOOF] Broadcasting as {mac} "
                            f"(cycle #{self._cycle_count})"
                        )
                    else:
                        self.log.error("[BLE-SPOOF] Failed to start advertisement.")
                else:
                    self.log.error(f"[BLE-SPOOF] Failed to set address {mac}")

                time.sleep(interval)

            except Exception as e:
                self.log.error(f"[BLE-SPOOF] Loop error: {e}")
                time.sleep(10)

    def status(self):
        return {
            "enabled":       self.cfg.get("ble_mac_spoof_enabled", False),
            "running":       self._running,
            "current_mac":   self._current_mac,
            "cycle_count":   self._cycle_count,
            "interface":     self._hci(),
        }
