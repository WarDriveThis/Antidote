# ble_inhale.py — Antidote Pi BLE collection engine
#
# Uses bleak (asyncio BLE library) to perform passive BLE scanning.
# Collects device MAC addresses, UUIDs, and local names from advertisements.
#
# bleak is a cross-platform BLE library backed by BlueZ on Linux.
# It uses asyncio — BleInhaleEngine.run_cycle() is a coroutine.

import asyncio
import time

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    print("[BLE] WARNING: bleak not installed. BLE inhale disabled.")


# Bluetooth SIG company identifier lookup.
# Loaded from data/company_ids.json — bundled snapshot of the official Bluetooth SIG
# assigned numbers list (via Nordic Semiconductor bluetooth-numbers-database).
# 3973 entries. IDs above ~0x1090 that return None are unassigned/proprietary.

import os as _os
import json as _json

def _load_company_ids():
    data_path = _os.path.join(_os.path.dirname(__file__), "data", "company_ids.json")
    try:
        with open(data_path) as f:
            return {e["code"]: e["name"] for e in _json.load(f)}
    except Exception:
        return {}

_COMPANY_IDS = _load_company_ids()


class BleInhaleEngine:
    def __init__(self, pool, config, logger):
        self.pool = pool
        self.cfg  = config
        self.log  = logger
        self._device_count = 0

        if not BLEAK_AVAILABLE:
            self.log.warn("[BLE] bleak unavailable — BLE inhale disabled.")

    def _handle_advertisement(self, device: "BLEDevice", adv: "AdvertisementData"):
        """Callback for each detected BLE advertisement."""
        self._device_count += 1

        # MAC address
        if self.cfg.get("collect_ble_mac") and device.address:
            self.pool.add(self.pool.CAT_BLE_MAC, device.address,
                          rssi=adv.rssi if adv else None)

        if adv is None:
            return

        # Local name (advertising name)
        if self.cfg.get("collect_ble_name"):
            name = adv.local_name or device.name
            if name and name.strip():
                self.pool.add(self.pool.CAT_BLE_NAME, name.strip())

        # Service UUIDs
        if self.cfg.get("collect_ble_uuid"):
            for uuid in (adv.service_uuids or []):
                self.pool.add(self.pool.CAT_BLE_UUID, str(uuid).upper())

        # v1.1: Manufacturer Specific Data
        # bleak surfaces this as {company_id_int: bytes}
        # Format stored: "CompanyName(XXXX):hexdata" or "XXXX:hexdata" if unknown
        if self.cfg.get("collect_ble_manuf"):
            for company_id, data in (adv.manufacturer_data or {}).items():
                payload_hex  = data.hex().upper()
                company_name = _COMPANY_IDS.get(company_id)
                if company_name:
                    manuf_str = f"{company_name}({company_id:04X}):{payload_hex}"
                else:
                    manuf_str = f"{company_id:04X}:{payload_hex}"
                self.pool.add(self.pool.CAT_BLE_MANUF, manuf_str,
                              rssi=adv.rssi)

    async def run_cycle_async(self) -> dict:
        """Async scan cycle — call from asyncio event loop."""
        if not BLEAK_AVAILABLE:
            return {"devices": 0, "error": "bleak unavailable"}

        self.log.info("[BLE] === BLE inhale cycle starting ===")
        self._device_count = 0

        duration = self.cfg.get("inhale_duration", 60)
        scan_time = max(10.0, min(float(duration), 60.0)) if duration > 0 else 30.0

        try:
            scanner = BleakScanner(detection_callback=self._handle_advertisement)
            await scanner.start()
            await asyncio.sleep(scan_time)
            await scanner.stop()
        except Exception as e:
            self.log.error(f"[BLE] Scan error: {e}")
            return {"devices": 0, "error": str(e)}

        stats = self.pool.stats()
        self.log.info(
            f"[BLE] Cycle complete. Advertisements seen={self._device_count}, "
            f"BLE MACs={stats['categories']['ble_mac']}, "
            f"UUIDs={stats['categories']['ble_uuid']}"
        )
        return {"devices": self._device_count, "pool": stats}

    def run_cycle(self) -> dict:
        """Synchronous wrapper — starts its own event loop."""
        return asyncio.run(self.run_cycle_async())
