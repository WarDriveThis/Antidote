# config.py — Antidote Pi v1.6
import json, os

CONFIG_FILE = "/home/kali/.antidote/config.json"

DEFAULTS = {
    # Inhale
    "inhale_duration":          60,
    "inhale_frequency":         300,
    "collect_ble_mac":          True,
    "collect_ble_uuid":         True,
    "collect_ble_name":         True,
    "collect_ble_manuf":        True,
    "collect_wifi_probe":       True,
    "collect_wifi_beacon":      True,
    "collect_wifi_assoc":       True,    # v1.8: AssoReq client MACs
    "collect_wifi_deauth":      True,    # v1.8: Deauth client MACs
    "wifi_interface":           "wlan1",
    "wifi_use_airmon":          True,
    "wifi_channel":             6,
    "scan_5ghz":                True,    # MT7610U AC600 supports 5GHz — enables UNII-1/3 capture
    "scan_5ghz_dfs":            False,   # Also scan DFS channels (52-140); more APs but iw may reject
    "wifi_primary_channels_only": False, # True = only ch 1,6,11 (faster sweeps, denser envs)
    "channel_dwell_sec":        1.0,     # seconds per channel during hop (was 0.5)
    # Pool
    "max_pool_size":            2000,
    "age_out_seconds":          7200,
    "pool_retention_hours":     2,
    # Exhale / UART
    "exhale_interval":          30,
    "uart_port":                "/dev/serial0",
    "uart_baud":                115200,
    "uart_sync_interval":       15,      # v1.9: was 30 — fresher pool on ESP32
    "uart_sample_size":         50,
    "exhale_enabled":           False,
    # SSID injection — wlan2 (PAU0A #2)
    "ssid_inject_enabled":      False,
    "ssid_inject_interface":    "wlan2",
    "ssid_inject_rate":         20,      # v1.9: was 5 — match real AP beacon density
    "ssid_inject_channels":     [1, 6, 11, 36, 40, 44, 48, 149, 165],  # v1.9: added 5GHz
    # BLE MAC spoofing — hci0 (Laird BL654 / nRF52840)
    "ble_mac_spoof_enabled":    False,
    "ble_mac_spoof_interface":  "hci0",
    "ble_mac_spoof_interval":   8,       # v1.9: was 30 — faster cycling defeats correlation
    # Management AP — wlan0 (Pi built-in, dedicated)
    "mgmt_ap_enabled":          False,
    "mgmt_ap_interface":        "wlan0",
    "mgmt_ap_ssid":             "Antidote",
    "mgmt_ap_password":         "SnoopThem",
    "mgmt_ap_channel":          1,
    # Web
    "web_host":                 "0.0.0.0",
    "web_port":                 5000,
    "configured":               False,
}


class Config:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            self._data = {**DEFAULTS, **saved}
            self._data["age_out_seconds"] = self._data["pool_retention_hours"] * 3600
            print(f"[CFG] Loaded from {CONFIG_FILE}")
        except (FileNotFoundError, json.JSONDecodeError):
            print("[CFG] No saved config, using defaults.")
            self._data = dict(DEFAULTS)

    def save(self):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def update(self, d):
        for k, v in d.items():
            if k in DEFAULTS:
                exp = type(DEFAULTS[k])
                if DEFAULTS[k] is None:
                    self._data[k] = v
                elif exp is bool:
                    self._data[k] = bool(v) if isinstance(v, bool) else str(v).lower() in ("true","1","on","yes")
                elif exp is int:
                    self._data[k] = int(v)
                elif exp is float:
                    self._data[k] = float(v)
                elif exp is list:
                    self._data[k] = v if isinstance(v, list) else self._data[k]
                else:
                    self._data[k] = str(v)
        if "pool_retention_hours" in d:
            self._data["age_out_seconds"] = self._data["pool_retention_hours"] * 3600

    def as_dict(self):
        return dict(self._data)

    def reset(self):
        self._data = dict(DEFAULTS)
        self.save()
