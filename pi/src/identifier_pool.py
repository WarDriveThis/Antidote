# identifier_pool.py — Antidote Pi v1.5
import time, random, threading


class IdentifierPool:
    CAT_BLE_MAC    = "ble_mac"
    CAT_BLE_UUID   = "ble_uuid"
    CAT_BLE_NAME   = "ble_name"
    CAT_BLE_MANUF  = "ble_manuf"
    CAT_WIFI_PROBE  = "wifi_probe_mac"
    CAT_WIFI_SSID   = "wifi_ssid"
    CAT_WIFI_BSSID  = "wifi_bssid"
    CAT_WIFI_CLIENT = "wifi_client_mac"   # v1.8: MACs from AssoReq / Deauth frames
    ALL_CATEGORIES = [
        CAT_BLE_MAC, CAT_BLE_UUID, CAT_BLE_NAME, CAT_BLE_MANUF,
        CAT_WIFI_PROBE, CAT_WIFI_SSID, CAT_WIFI_BSSID, CAT_WIFI_CLIENT,
    ]

    def __init__(self, max_size=2000, age_out_seconds=7200):
        self.max_size          = max_size
        self.age_out_seconds   = age_out_seconds
        self._pool             = {}
        self._lock             = threading.Lock()
        self._cat_counts       = {c: 0 for c in self.ALL_CATEGORIES}
        self._cat_last_updated = {c: 0.0 for c in self.ALL_CATEGORIES}
        print(f"[POOL] Ready. max={max_size}, age_out={age_out_seconds}s")

    def add(self, category, value, rssi=None, channel=None):
        if not value:
            return
        value = str(value).strip().upper() if ("mac" in category or "bssid" in category) else str(value).strip()
        key = f"{category}:{value}"
        now = time.time()
        with self._lock:
            # BLE name deduplication: if a shorter version of this name exists,
            # remove it and keep only the longest form. BLE devices often advertise
            # both "Shortened Local Name" (0x08) and "Complete Local Name" (0x09)
            # in different packets — bleak surfaces both; we keep the longest.
            if category == self.CAT_BLE_NAME and key not in self._pool:
                # Check if we have any existing name that is a prefix of the new value
                # OR the new value is a prefix of an existing name
                for existing_key in list(self._pool.keys()):
                    ev = self._pool[existing_key]
                    if ev["cat"] != self.CAT_BLE_NAME:
                        continue
                    existing_val = ev["value"]
                    # New value is longer — it supersedes the stored shorter one
                    if value.startswith(existing_val) and len(value) > len(existing_val):
                        del self._pool[existing_key]
                        break
                    # New value is shorter — the stored name is already better, discard new
                    if existing_val.startswith(value) and len(existing_val) > len(value):
                        # Just refresh timestamp on the longer entry and return
                        self._pool[existing_key]["last_seen"] = now
                        self._pool[existing_key]["count"] += 1
                        return

            if key in self._pool:
                self._pool[key]["last_seen"] = now
                self._pool[key]["count"] += 1
                if rssi is not None:
                    self._pool[key]["rssi"] = rssi
            else:
                if len(self._pool) >= self.max_size:
                    self._evict_oldest()
                self._pool[key] = {
                    "cat": category, "value": value,
                    "first_seen": now, "last_seen": now,
                    "count": 1, "rssi": rssi, "channel": channel,
                }
            new_count = sum(1 for v in self._pool.values() if v["cat"] == category)
            if new_count > self._cat_counts.get(category, 0):
                self._cat_counts[category] = new_count
                self._cat_last_updated[category] = now

    def add_many(self, category, values, **kwargs):
        for v in values:
            self.add(category, v, **kwargs)

    def _evict_oldest(self):
        if self._pool:
            oldest = min(self._pool, key=lambda k: self._pool[k]["last_seen"])
            del self._pool[oldest]

    def age_out(self):
        cutoff = time.time() - self.age_out_seconds
        with self._lock:
            stale = [k for k, v in self._pool.items() if v["last_seen"] < cutoff]
            for k in stale:
                del self._pool[k]
        if stale:
            print(f"[POOL] Aged out {len(stale)}. Remaining: {len(self._pool)}")
        return len(stale)

    def count(self):
        with self._lock:
            return len(self._pool)

    def count_by_category(self):
        counts = {c: 0 for c in self.ALL_CATEGORIES}
        with self._lock:
            for v in self._pool.values():
                if v["cat"] in counts:
                    counts[v["cat"]] += 1
        return counts

    def get_by_category(self, category):
        with self._lock:
            return [v["value"] for v in self._pool.values() if v["cat"] == category]

    def get_sample_by_category(self, n=5):
        result = {}
        with self._lock:
            for cat in self.ALL_CATEGORIES:
                vals = [v["value"] for v in self._pool.values() if v["cat"] == cat]
                result[cat] = random.sample(vals, min(n, len(vals))) if vals else []
        return result

    def category_freshness(self):
        now = time.time()
        return {
            cat: (now - self._cat_last_updated[cat]) if self._cat_last_updated[cat] > 0 else None
            for cat in self.ALL_CATEGORIES
        }

    def get_random_sample(self, n=50, categories=None):
        with self._lock:
            candidates = [v for v in self._pool.values()
                          if not categories or v["cat"] in categories]
        if not candidates:
            return []
        return [{"cat": e["cat"], "value": e["value"]}
                for e in random.sample(candidates, min(n, len(candidates)))]

    def stats(self):
        return {
            "total":      self.count(),
            "max_size":   self.max_size,
            "categories": self.count_by_category(),
            "freshness":  self.category_freshness(),
        }
