# ssid_inject.py — Antidote Pi SSID Beacon Injection Engine v1.5
#
# Injects 802.11 beacon frames using SSIDs from the identifier pool.
# Each beacon uses a randomly generated BSSID so injected frames are
# logged by passive scanners as distinct "ghost" access points.
#
# Self-filtering: all injected BSSIDs are registered in SelfFilter so
# the capture engine ignores frames we injected ourselves.
#
# Interface: wlan1mon (wlan1 put into monitor mode at startup)
# Requires: scapy, wlan1 adapter with injection support (MT7610U / PAU0A)

import threading
import time
import random
import subprocess
import logging

log = logging.getLogger("ssid_inject")

try:
    from scapy.all import sendp, conf as scapy_conf
    from scapy.layers.dot11 import (
        RadioTap, Dot11, Dot11Beacon, Dot11Elt
    )
    SCAPY_OK = True
except ImportError:
    SCAPY_OK = False
    log.warning("[SSID] scapy not available — injection disabled")

# Standard supported rates payload
_RATES      = b"\x82\x84\x8b\x96\x0c\x12\x18\x24"
_RATES_EXT  = b"\x30\x48\x60\x6c"


def _random_mac() -> str:
    """Generate a locally-administered, unicast random MAC."""
    b = [random.randint(0, 255) for _ in range(6)]
    b[0] = (b[0] & 0xFE) | 0x02   # locally administered, unicast
    return ":".join(f"{x:02x}" for x in b)


def _build_beacon(ssid: str, bssid: str, channel: int) -> object:
    return (
        RadioTap() /
        Dot11(type=0, subtype=8,
              addr1="ff:ff:ff:ff:ff:ff",
              addr2=bssid,
              addr3=bssid) /
        Dot11Beacon(cap="ESS+privacy") /
        Dot11Elt(ID=0,  info=ssid.encode("utf-8", errors="replace")[:32]) /
        Dot11Elt(ID=1,  info=_RATES) /
        Dot11Elt(ID=3,  info=bytes([channel])) /
        Dot11Elt(ID=50, info=_RATES_EXT)
    )


class SelfFilter:
    """Shared set of BSSIDs we injected — used by wifi_inhale to skip own frames."""
    def __init__(self):
        self._bssids: set = set()
        self._lock = threading.Lock()

    def add(self, bssid: str):
        with self._lock:
            self._bssids.add(bssid.upper())

    def is_own(self, bssid: str) -> bool:
        with self._lock:
            return bssid.upper() in self._bssids

    def clear_old(self, keep: set):
        """Prune BSSIDs no longer in the active inject set."""
        with self._lock:
            self._bssids &= {b.upper() for b in keep}


class SsidInjector:
    def __init__(self, pool, config, logger, self_filter: SelfFilter):
        self.pool        = pool
        self.cfg         = config
        self.log         = logger
        self.self_filter = self_filter
        self._thread     = None
        self._running       = False
        # ssid -> bssid mapping — stable per session so each SSID has a consistent ghost AP
        self._ssid_bssid: dict = {}
        # Status tracking
        self._last_ssid     = None
        self._last_bssid    = None
        self._beacon_count  = 0

    def status(self):
        return {
            "enabled":      self.cfg.get("ssid_inject_enabled", False),
            "running":      self._running,
            "last_ssid":    self._last_ssid,
            "last_bssid":   self._last_bssid,
            "beacon_count": self._beacon_count,
        }

    def start(self):
        if not SCAPY_OK:
            self.log.error("[SSID] Cannot start — scapy not installed.")
            return
        if not self.cfg.get("ssid_inject_enabled", False):
            self.log.info("[SSID] Injection disabled in config.")
            return
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log.info("[SSID] Injection engine started.")

    def stop(self):
        self._running = False

    def _ensure_monitor(self) -> str:
        """Put inject interface into monitor mode using iw. Return monitor iface name."""
        iface = self.cfg.get("ssid_inject_interface", "wlan2")
        mon   = iface + "mon"
        try:
            result = subprocess.run(
                ["iwconfig", mon], capture_output=True, text=True)
            if "Monitor" in result.stdout:
                self.log.info(f"[SSID] {mon} already in monitor mode.")
                return mon
        except Exception:
            pass
        try:
            subprocess.run(["nmcli", "device", "set", iface, "managed", "no"],
                           capture_output=True, timeout=5)
            subprocess.run(["ip", "link", "set", iface, "down"],
                           capture_output=True, timeout=5)
            time.sleep(0.3)
            r = subprocess.run(
                ["iw", "dev", iface, "interface", "add", mon, "type", "monitor"],
                capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                subprocess.run(["iw", "dev", iface, "set", "type", "monitor"],
                               capture_output=True, timeout=5)
                subprocess.run(["ip", "link", "set", iface, "up"],
                               capture_output=True, timeout=5)
                time.sleep(1)
                self.log.info(f"[SSID] {iface} set to monitor mode (in-place).")
                return iface
            subprocess.run(["ip", "link", "set", mon, "up"],
                           capture_output=True, timeout=5)
            subprocess.run(["ip", "link", "set", iface, "up"],
                           capture_output=True, timeout=5)
            time.sleep(1)
            self.log.info(f"[SSID] Monitor interface {mon} ready.")
            return mon
        except Exception as e:
            self.log.error(f"[SSID] Failed to start monitor mode: {e}")
            return mon

    def _get_ssid_bssid(self, ssid: str) -> str:
        """Return stable BSSID for this SSID, creating one if needed."""
        if ssid not in self._ssid_bssid:
            mac = _random_mac()
            self._ssid_bssid[ssid] = mac
            self.self_filter.add(mac)
        return self._ssid_bssid[ssid]

    def _run(self):
        scapy_conf.verb = 0
        mon_iface = self._ensure_monitor()
        channels  = self.cfg.get("ssid_inject_channels", [1, 6, 11])
        rate      = self.cfg.get("ssid_inject_rate", 5)
        interval  = 1.0 / max(rate, 1)
        ch_idx    = 0

        self.log.info(f"[SSID] Injecting on {mon_iface}, channels={channels}")

        while self._running:
            try:
                ssids = self.pool.get_by_category(self.pool.CAT_WIFI_SSID)
                if not ssids:
                    time.sleep(5)
                    continue

                # Rotate through channels
                channel = channels[ch_idx % len(channels)]
                ch_idx += 1
                try:
                    subprocess.run(
                        ["iwconfig", mon_iface, "channel", str(channel)],
                        capture_output=True, timeout=2)
                except Exception:
                    pass

                # Inject one beacon per SSID per channel rotation
                injected = 0
                for ssid in ssids[:50]:   # cap at 50 SSIDs per burst
                    if not self._running:
                        break
                    bssid  = self._get_ssid_bssid(ssid)
                    frame  = _build_beacon(ssid, bssid, channel)
                    try:
                        sendp(frame, iface=mon_iface, count=1,
                              verbose=False, inter=0)
                        injected += 1
                        self._last_ssid  = ssid
                        self._last_bssid = bssid
                        self._beacon_count += 1
                    except Exception as e:
                        self.log.error(f"[SSID] Send error: {e}")
                        break
                    time.sleep(interval)

                # Prune stale BSSID mappings
                active = set(self._ssid_bssid.keys())
                pool_ssids = set(ssids)
                stale = active - pool_ssids
                for s in stale:
                    del self._ssid_bssid[s]
                self.self_filter.clear_old(set(self._ssid_bssid.values()))

                if injected:
                    self.log.debug(f"[SSID] Injected {injected} beacons on ch{channel}")

            except Exception as e:
                self.log.error(f"[SSID] Loop error: {e}")
                time.sleep(5)
