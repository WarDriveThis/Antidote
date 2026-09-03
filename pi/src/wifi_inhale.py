# wifi_inhale.py — Antidote Pi WiFi collection engine v1.8
#
# v1.8 changes:
#   - Added Dot11AssoReq collection (client MACs joining nearby APs)
#   - Added Dot11Deauth collection (client MACs on disconnect)
#   - Both gated by config flags collect_wifi_assoc / collect_wifi_deauth
#
# v1.5 changes:
#   - SelfFilter integration: frames from our own injected BSSIDs are skipped
#   - wlan1 monitor mode setup moved to ssid_inject.py (inject engine owns wlan1)
#   - wlan0 capture and wlan1 inject are fully independent
#
# wlan0mon is created ONCE at service start and kept alive for the entire
# service lifetime. Per-cycle teardown caused ghost interfaces.
#   - setup_service(): called once at startup — creates wlan0mon
#   - run_cycle():     sniffs on persistent wlan0mon
#   - teardown_service(): called at shutdown — removes wlan0mon cleanly

import threading
import time
import subprocess

try:
    from scapy.all import sniff, Dot11, Dot11Beacon, Dot11ProbeReq, Dot11Elt
    from scapy.layers.dot11 import Dot11AssoReq, Dot11Deauth
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    print("[WIFI] WARNING: scapy not installed. WiFi capture disabled.")

# 2.4 GHz: all 13 channels, or just the 3 non-overlapping primaries (faster/denser)
CHANNELS_2GHZ_ALL     = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
CHANNELS_2GHZ_PRIMARY = [1, 6, 11]

# 5 GHz non-DFS channels (safe with country 99 / US regulatory domain).
# UNII-1 (5180-5240 MHz): channels 36, 40, 44, 48
# UNII-3 (5745-5825 MHz): channels 149, 153, 157, 161, 165
# These do not require DFS/CAC and iw accepts them in monitor mode.
CHANNELS_5GHZ_SAFE = [36, 40, 44, 48, 149, 153, 157, 161, 165]

# DFS 5 GHz channels — UNII-2A (5260-5320) and UNII-2C (5500-5700 MHz).
# Many APs use these. Usable in passive monitor/receive mode (no TX required).
# iw may reject channel-set on these if regulatory domain is strict.
# Enable via config: scan_5ghz_dfs=True
CHANNELS_5GHZ_DFS  = [52, 56, 60, 64, 100, 104, 108, 112, 116, 132, 136, 140]

CHANNEL_DWELL_SEC = 1.0   # dwell per channel in seconds (was 0.5; longer = more beacons caught)


def _set_channel(iface, channel):
    try:
        subprocess.run(["iw", "dev", iface, "set", "channel", str(channel)],
                       capture_output=True, timeout=2)
    except Exception:
        pass


def _iface_exists(name):
    r = subprocess.run(["ip", "link", "show", name], capture_output=True, timeout=3)
    return r.returncode == 0


def _setup_monitor_persistent(phys_iface, logger):
    # Uses iw-based monitor mode — works natively with MT7610U (PAU0A).
    # No airmon-ng, no nexmon, no NM disruption.
    mon_iface = phys_iface + "mon"

    # Reuse if already in monitor mode
    if _iface_exists(mon_iface):
        r = subprocess.run(["iwconfig", mon_iface], capture_output=True, text=True, timeout=3)
        if "Monitor" in r.stdout:
            logger.info(f"[WIFI] {mon_iface} already in monitor mode, reusing.")
            subprocess.run(["ip", "link", "set", mon_iface, "up"], capture_output=True)
            return True, mon_iface
        logger.info(f"[WIFI] Removing stale {mon_iface}.")
        subprocess.run(["iw", "dev", mon_iface, "del"], capture_output=True, timeout=5)
        time.sleep(1)

    # Tell NetworkManager to leave this interface alone
    subprocess.run(["nmcli", "device", "set", phys_iface, "managed", "no"],
                   capture_output=True, timeout=5)

    # Bring physical interface down before mode change
    subprocess.run(["ip", "link", "set", phys_iface, "down"], capture_output=True, timeout=5)
    time.sleep(0.5)

    # Create named monitor interface (e.g. wlan1mon)
    r = subprocess.run(
        ["iw", "dev", phys_iface, "interface", "add", mon_iface, "type", "monitor"],
        capture_output=True, text=True, timeout=5
    )

    if r.returncode != 0:
        # Fallback: convert phys_iface in-place
        logger.info(f"[WIFI] add interface failed ({r.stderr.strip()}), trying in-place.")
        subprocess.run(["iw", "dev", phys_iface, "set", "type", "monitor"],
                       capture_output=True, timeout=5)
        subprocess.run(["ip", "link", "set", phys_iface, "up"], capture_output=True, timeout=5)
        time.sleep(1)
        r2 = subprocess.run(["iwconfig", phys_iface], capture_output=True, text=True, timeout=3)
        if "Monitor" in r2.stdout:
            logger.info(f"[WIFI] {phys_iface} set to monitor mode (in-place).")
            return True, phys_iface
        logger.error(f"[WIFI] Failed to set monitor mode on {phys_iface}.")
        return False, mon_iface

    subprocess.run(["ip", "link", "set", mon_iface, "up"], capture_output=True, timeout=5)
    subprocess.run(["ip", "link", "set", phys_iface, "up"], capture_output=True, timeout=5)

    for _ in range(8):
        time.sleep(1)
        r = subprocess.run(["iwconfig", mon_iface], capture_output=True, text=True, timeout=3)
        if "Monitor" in r.stdout:
            logger.info(f"[WIFI] Monitor interface {mon_iface} ready (iw, persistent).")
            return True, mon_iface

    logger.error(f"[WIFI] {mon_iface} did not come UP.")
    return False, mon_iface


def _teardown_monitor_persistent(phys_iface, logger):
    mon_iface = phys_iface + "mon"
    try:
        subprocess.run(["ip", "link", "set", mon_iface, "down"], capture_output=True, timeout=5)
        subprocess.run(["iw", "dev", mon_iface, "del"], capture_output=True, timeout=5)
        subprocess.run(["iw", "dev", phys_iface, "set", "type", "managed"],
                       capture_output=True, timeout=5)
        subprocess.run(["ip", "link", "set", phys_iface, "up"], capture_output=True, timeout=5)
        subprocess.run(["nmcli", "device", "set", phys_iface, "managed", "yes"],
                       capture_output=True, timeout=5)
        logger.info(f"[WIFI] {mon_iface} removed at shutdown.")
    except Exception as e:
        logger.warn(f"[WIFI] Teardown warning: {e}")


class WifiInhaleEngine:
    def __init__(self, pool, config, logger, self_filter=None):
        self.pool         = pool
        self.cfg          = config
        self.log          = logger
        self.self_filter  = self_filter   # v1.5: SelfFilter instance from ssid_inject
        self._hopping     = False
        self._hop_thread  = None
        self._frame_count = 0
        self._monitor_iface  = None
        self._service_ready  = False

        if not SCAPY_AVAILABLE:
            self.log.warn("[WIFI] scapy unavailable — WiFi inhale disabled.")

    @property
    def _phys_iface(self):
        return self.cfg.get("wifi_interface", "wlan0")

    def setup_service(self):
        if not SCAPY_AVAILABLE:
            return
        ok, mon = _setup_monitor_persistent(self._phys_iface, self.log)
        if ok:
            self._monitor_iface = mon
            self._service_ready = True
        else:
            self.log.error("[WIFI] Failed to create persistent monitor interface.")

    def teardown_service(self):
        if self._monitor_iface:
            _teardown_monitor_persistent(self._phys_iface, self.log)
        self._monitor_iface = None
        self._service_ready = False

    def _build_channel_list(self):
        """Build the channel scan list based on config.
        scan_5ghz=True       — add UNII-1/3 non-DFS 5GHz channels (safe on all regulatory domains)
        scan_5ghz_dfs=True   — also add UNII-2A/2C DFS channels (more APs, but iw may reject
                               channel-set on some regulatory configs; errors are silently skipped)
        wifi_primary_channels_only=True — 2.4GHz: use only [1,6,11] for faster sweeps
        """
        use_5ghz     = self.cfg.get("scan_5ghz", True)
        use_dfs      = self.cfg.get("scan_5ghz_dfs", False)
        primary_only = self.cfg.get("wifi_primary_channels_only", False)
        channels = CHANNELS_2GHZ_PRIMARY if primary_only else CHANNELS_2GHZ_ALL
        if use_5ghz:
            channels = channels + CHANNELS_5GHZ_SAFE
        if use_5ghz and use_dfs:
            channels = channels + CHANNELS_5GHZ_DFS
        return channels

    def _start_channel_hop(self):
        self._hopping = True
        channels = self._build_channel_list()
        dwell = self.cfg.get("channel_dwell_sec", CHANNEL_DWELL_SEC)
        def _hop():
            idx = 0
            while self._hopping:
                ch = channels[idx % len(channels)]
                if self._monitor_iface:
                    _set_channel(self._monitor_iface, ch)
                time.sleep(dwell)
                idx += 1
        self._hop_thread = threading.Thread(target=_hop, daemon=True)
        self._hop_thread.start()

    def _stop_channel_hop(self):
        self._hopping = False
        if self._hop_thread:
            self._hop_thread.join(timeout=2)
            self._hop_thread = None

    def _own_ssids(self):
        """Return set of SSIDs we generate ourselves — AP SSID and any injected SSIDs.
        These must not appear in the collected pool."""
        own = set()
        ap_ssid = self.cfg.get("mgmt_ap_ssid", "").strip()
        if ap_ssid:
            own.add(ap_ssid)
        return own

    def _handle_frame(self, pkt):
        if not pkt.haslayer(Dot11):
            return
        dot11 = pkt[Dot11]

        # v1.5: skip frames from our own injected BSSIDs (by MAC)
        if self.self_filter:
            for addr in (dot11.addr1, dot11.addr2, dot11.addr3):
                if addr and self.self_filter.is_own(addr):
                    return

        own_ssids = self._own_ssids()

        if pkt.haslayer(Dot11ProbeReq):
            src_mac = dot11.addr2
            if src_mac and self.cfg.get("collect_wifi_probe"):
                self.pool.add(self.pool.CAT_WIFI_PROBE, src_mac)
            elt = pkt[Dot11Elt] if pkt.haslayer(Dot11Elt) else None
            while elt:
                if elt.ID == 0 and elt.info:
                    try:
                        ssid = elt.info.decode("utf-8", errors="ignore").strip()
                        if ssid and ssid not in own_ssids and self.cfg.get("collect_wifi_beacon"):
                            self.pool.add(self.pool.CAT_WIFI_SSID, ssid)
                    except Exception:
                        pass
                elt = elt.payload if hasattr(elt, "payload") and isinstance(elt.payload, Dot11Elt) else None

        elif pkt.haslayer(Dot11Beacon):
            bssid = dot11.addr3
            if bssid and self.cfg.get("collect_wifi_beacon"):
                self.pool.add(self.pool.CAT_WIFI_BSSID, bssid)
            elt = pkt[Dot11Elt] if pkt.haslayer(Dot11Elt) else None
            while elt:
                if elt.ID == 0 and elt.info:
                    try:
                        ssid = elt.info.decode("utf-8", errors="ignore").strip()
                        if ssid and ssid not in own_ssids and self.cfg.get("collect_wifi_beacon"):
                            self.pool.add(self.pool.CAT_WIFI_SSID, ssid)
                    except Exception:
                        pass
                elt = elt.payload if hasattr(elt, "payload") and isinstance(elt.payload, Dot11Elt) else None

        # v1.8: Association requests — fired when a client joins any nearby AP.
        # addr2 = client MAC (the most reliable source of connected-device MACs).
        elif pkt.haslayer(Dot11AssoReq):
            if self.cfg.get("collect_wifi_assoc", True):
                client_mac = dot11.addr2
                if client_mac:
                    self.pool.add(self.pool.CAT_WIFI_CLIENT, client_mac)

        # v1.8: Deauthentication frames — fired when a client disconnects.
        # addr2 = client MAC (or AP MAC when AP-initiated; both are useful).
        elif pkt.haslayer(Dot11Deauth):
            if self.cfg.get("collect_wifi_deauth", True):
                client_mac = dot11.addr2
                if client_mac:
                    self.pool.add(self.pool.CAT_WIFI_CLIENT, client_mac)

        self._frame_count += 1

    def run_cycle(self, stop_event=None):
        if not SCAPY_AVAILABLE:
            return {"frames": 0, "error": "scapy unavailable"}

        self.log.info("[WIFI] === WiFi inhale cycle starting ===")
        self._frame_count = 0

        if not self._monitor_iface or not _iface_exists(self._monitor_iface):
            self.log.error(f"[WIFI] Monitor interface missing — attempting recovery.")
            self.setup_service()
            if not self._service_ready:
                return {"frames": 0, "error": "monitor interface unavailable"}

        _set_channel(self._monitor_iface, self.cfg.get("wifi_channel", 6))
        self._start_channel_hop()
        duration = self.cfg.get("inhale_duration", 60)

        try:
            sniff(
                iface       = self._monitor_iface,
                prn         = self._handle_frame,
                store       = False,
                timeout     = duration if duration > 0 else None,
                stop_filter = (lambda p: stop_event.is_set()) if stop_event else None,
            )
        except Exception as e:
            self.log.error(f"[WIFI] Sniff error: {e}")
        finally:
            self._stop_channel_hop()

        self.pool.age_out()
        stats = self.pool.stats()
        self.log.info(
            f"[WIFI] Cycle complete. Frames={self._frame_count}, "
            f"Pool={stats['total']}, probes={stats['categories']['wifi_probe_mac']}, "
            f"SSIDs={stats['categories']['wifi_ssid']}, "
            f"clients={stats['categories']['wifi_client_mac']}"
        )
        return {"frames": self._frame_count, "pool": stats}
