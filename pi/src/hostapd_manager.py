# hostapd_manager.py — Antidote v1.6 Pi Management AP v1.5
#
# Starts a WPA2 access point on wlan0 (Pi built-in BCM43430).
# The Antidote web UI is accessible from devices connected to this AP
# at http://192.168.4.1:5000 — no LAN connection required.
#
# Prerequisites:
#   sudo apt install hostapd dnsmasq
#   wlan0 must not be managed by NetworkManager
#
# The AP runs independently of the capture/inject interfaces.
# hostapd config is written to /tmp/antidote_hostapd.conf on each start.

import subprocess
import time
import os
import logging

log = logging.getLogger("hostapd_mgr")

_HOSTAPD_CONF  = "/tmp/antidote_hostapd.conf"
_DNSMASQ_CONF  = "/tmp/antidote_dnsmasq.conf"
_AP_IP         = "192.168.4.1"
_AP_NETMASK    = "255.255.255.0"
_DHCP_START    = "192.168.4.10"
_DHCP_END      = "192.168.4.50"


class HostapdManager:
    def __init__(self, config, logger):
        self.cfg     = config
        self.log     = logger
        self._hostapd_proc  = None
        self._dnsmasq_proc  = None

    def start(self):
        if not self.cfg.get("mgmt_ap_enabled", False):
            self.log.info("[AP] Management AP disabled in config.")
            return
        iface = self.cfg.get("mgmt_ap_interface", "wlan0")
        ssid  = self.cfg.get("mgmt_ap_ssid", "Antidote")
        pw    = self.cfg.get("mgmt_ap_password", "SnoopThem")
        ch    = self.cfg.get("mgmt_ap_channel", 1)

        if not self._iface_exists(iface):
            self.log.error(f"[AP] Interface {iface} not found — is second dongle connected?")
            return

        self._configure_iface(iface)
        self._write_hostapd_conf(iface, ssid, pw, ch)
        self._write_dnsmasq_conf(iface)
        self._start_hostapd()
        self._start_dnsmasq()
        self.log.info(f"[AP] Management AP '{ssid}' started on {iface} ({_AP_IP})")
        self.log.info(f"[AP] Web UI accessible at http://{_AP_IP}:5000")

    def stop(self):
        if self._hostapd_proc:
            self._hostapd_proc.terminate()
        if self._dnsmasq_proc:
            self._dnsmasq_proc.terminate()
        self.log.info("[AP] Management AP stopped.")

    def _iface_exists(self, iface: str) -> bool:
        return os.path.exists(f"/sys/class/net/{iface}")

    def _configure_iface(self, iface: str):
        """Bring up interface, set static IP, mark unmanaged by NM."""
        subprocess.run(["nmcli", "device", "set", iface, "managed", "no"],
                       capture_output=True)
        subprocess.run(["ip", "link", "set", iface, "up"], capture_output=True)
        subprocess.run(["ip", "addr", "flush", "dev", iface], capture_output=True)
        subprocess.run(["ip", "addr", "add",
                        f"{_AP_IP}/{_AP_NETMASK}", "dev", iface],
                       capture_output=True)

    def _write_hostapd_conf(self, iface, ssid, password, channel):
        conf = f"""interface={iface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
        with open(_HOSTAPD_CONF, "w") as f:
            f.write(conf)

    def _write_dnsmasq_conf(self, iface):
        conf = f"""interface={iface}
dhcp-range={_DHCP_START},{_DHCP_END},255.255.255.0,24h
dhcp-option=3,{_AP_IP}
dhcp-option=6,{_AP_IP}
server=8.8.8.8
log-queries
log-dhcp
"""
        with open(_DNSMASQ_CONF, "w") as f:
            f.write(conf)

    def _start_hostapd(self):
        # Kill any existing hostapd
        subprocess.run(["pkill", "-f", "antidote_hostapd"], capture_output=True)
        time.sleep(0.5)
        self._hostapd_proc = subprocess.Popen(
            ["hostapd", _HOSTAPD_CONF],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def _start_dnsmasq(self):
        subprocess.run(["pkill", "-f", "antidote_dnsmasq"], capture_output=True)
        time.sleep(0.3)
        self._dnsmasq_proc = subprocess.Popen(
            ["dnsmasq", f"--conf-file={_DNSMASQ_CONF}",
             "--pid-file=/tmp/antidote_dnsmasq.pid"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
