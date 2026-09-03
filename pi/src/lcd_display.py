#!/usr/bin/env python3
# lcd_display.py — Antidote LCD Hat Display Service v1.9
#
# Drives the Waveshare Zero LCD Hat (A):
#   Center:  1.3"  240×240  ST7789  — Pool counts dashboard
#   Left:    0.96" 160×80   ST7735S — Service health status
#   Right:   0.96" 160×80   ST7735S — Scrolling ID ticker
#
# Runs as a separate systemd service (antidote-lcd.service).
# Reads from Antidote's /api/status endpoint every 3 seconds.
# Zero impact on core Antidote service — read-only, no shared state.
#
# GPIO (no conflicts with Antidote UART on GPIO14/15):
#   SPI MOSI: GPIO10   SPI CLK: GPIO11
#   CE0: GPIO8 (center)  CE1: GPIO7 (sides — check your hat revision)
#   DC:  GPIO24          RST: GPIO25
#   BL:  GPIO13 (backlight PWM)
#   Key1: GPIO21 — trigger manual inhale via /api/action/inhale
#   Key2: GPIO20 — cycle right panel view
#
# Dependencies:
#   pip install pillow luma.lcd luma.core RPi.GPIO requests
#   (luma.lcd handles ST7789/ST7735S over SPI)
#
# Install:
#   sudo cp antidote-lcd.service /etc/systemd/system/
#   sudo systemctl enable antidote-lcd.service
#   sudo systemctl start antidote-lcd.service

import time
import threading
import requests
import logging
import sys
import os

log = logging.getLogger("antidote-lcd")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [LCD] %(message)s",
                    datefmt="%H:%M:%S")

# ── Configuration ────────────────────────────────────────────────
API_BASE        = "http://127.0.0.1:5000"
POLL_INTERVAL   = 3       # seconds between API polls
TICKER_SPEED    = 0.4     # seconds per scroll step on right panel
BACKLIGHT_PIN   = 13      # GPIO for backlight (PWM)
KEY1_PIN        = 21      # GPIO for Key1 — manual inhale
KEY2_PIN        = 20      # GPIO for Key2 — cycle right panel view

# Category display order and labels for center panel
CAT_CONFIG = [
    ("wifi_probe_mac",  "Probes",   (0x4C, 0xAF, 0xFF)),   # blue
    ("wifi_ssid",       "SSIDs",    (0x4C, 0xFF, 0x9F)),   # green
    ("wifi_bssid",      "BSSIDs",   (0x4C, 0xFF, 0x9F)),   # green
    ("wifi_client_mac", "Clients",  (0xFF, 0xC8, 0x4C)),   # amber
    ("ble_mac",         "BLE MACs", (0xC8, 0x4C, 0xFF)),   # purple
    ("ble_name",        "BLE Names",(0xC8, 0x4C, 0xFF)),   # purple
    ("ble_manuf",       "Manuf",    (0x88, 0x44, 0xCC)),   # dark purple
]

# Freshness thresholds (seconds) → colour multiplier
FRESH_GREEN  = 300    # < 5 min  → full colour
FRESH_AMBER  = 900    # < 15 min → amber tint
# > 15 min  → dim / grey


# ── Luma/PIL import with graceful fallback ────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False
    log.error("Pillow not installed. Run: pip install pillow")

try:
    from luma.core.interface.serial import spi
    from luma.lcd.device import st7789, st7735
    LUMA_OK = True
except ImportError:
    LUMA_OK = False
    log.error("luma.lcd not installed. Run: pip install luma.lcd")

try:
    import RPi.GPIO as GPIO
    GPIO_OK = True
except ImportError:
    GPIO_OK = False
    log.warning("RPi.GPIO not installed — buttons disabled")


# ── Display helpers ──────────────────────────────────────────────
def _age_color(base_rgb, age_seconds):
    """Tint colour based on data age. Fresh=bright, stale=grey."""
    r, g, b = base_rgb
    if age_seconds is None or age_seconds > FRESH_AMBER:
        return (80, 80, 80)     # grey — stale
    if age_seconds > FRESH_GREEN:
        # interpolate toward amber
        t = (age_seconds - FRESH_GREEN) / (FRESH_AMBER - FRESH_GREEN)
        r = int(r + (0xFF - r) * t * 0.6)
        g = int(g * (1 - t * 0.4))
        b = int(b * (1 - t * 0.6))
    return (min(255, r), min(255, g), min(255, b))


def _make_font(size=14):
    """Load a font, falling back to default if not found."""
    try:
        # Try common monospace fonts on Kali/Debian
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        ]:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    except Exception:
        pass
    return ImageFont.load_default()


# ── Panel renderers ──────────────────────────────────────────────
class CenterPanel:
    """240×240 pool counts dashboard."""
    W, H = 240, 240

    def __init__(self):
        self._font_lg = _make_font(32)
        self._font_sm = _make_font(13)
        self._font_hd = _make_font(15)

    def render(self, status: dict) -> Image.Image:
        img  = Image.new("RGB", (self.W, self.H), (8, 8, 20))
        draw = ImageDraw.Draw(img)

        cats     = status.get("pool", {}).get("categories", {})
        fresh    = status.get("pool", {}).get("freshness", {})
        total    = status.get("pool", {}).get("total", 0)
        mode     = status.get("mode", "?")
        uptime   = status.get("uptime", "--")

        # Header bar
        mode_color = {
            "INHALE": (0x4C, 0xAF, 0xFF),
            "EXHALE": (0xFF, 0xC8, 0x4C),
            "ERROR":  (0xFF, 0x44, 0x44),
        }.get(mode, (0x44, 0xFF, 0x44))
        draw.rectangle([(0, 0), (self.W, 28)], fill=(18, 18, 40))
        draw.text((6, 4),  "ANTIDOTE",    font=self._font_hd, fill=(180, 180, 220))
        draw.text((130, 4), mode,         font=self._font_hd, fill=mode_color)
        draw.text((6, 220), f"Pool: {total}", font=self._font_sm, fill=(140, 140, 170))
        draw.text((130, 220), uptime,       font=self._font_sm, fill=(100, 100, 130))

        # Category rows — 7 rows in 190px
        row_h = 27
        y_start = 32
        now = time.time()

        for i, (cat_key, label, base_rgb) in enumerate(CAT_CONFIG):
            count = cats.get(cat_key, 0)
            last_update = fresh.get(cat_key)
            age = (now - last_update) if last_update else None
            color = _age_color(base_rgb, age)
            y = y_start + i * row_h

            # Row background alternating
            if i % 2 == 0:
                draw.rectangle([(0, y), (self.W, y + row_h - 1)], fill=(14, 14, 28))

            # Count (large, right-aligned in first 70px)
            count_str = str(count) if count < 10000 else f"{count//1000}k"
            draw.text((4, y + 3), count_str, font=self._font_lg, fill=color)

            # Label
            draw.text((78, y + 8), label, font=self._font_sm, fill=(180, 180, 200))

            # Freshness dot
            dot_color = (0x44, 0xFF, 0x44) if (age and age < FRESH_GREEN) else \
                        (0xFF, 0xC8, 0x44) if (age and age < FRESH_AMBER) else \
                        (0x88, 0x44, 0x44)
            draw.ellipse([(228, y + 8), (238, y + 18)], fill=dot_color)

        return img


class LeftPanel:
    """160×80 service health panel."""
    W, H = 160, 80

    def __init__(self):
        self._font = _make_font(11)
        self._font_hd = _make_font(12)

    def render(self, status: dict) -> Image.Image:
        img  = Image.new("RGB", (self.W, self.H), (8, 8, 20))
        draw = ImageDraw.Draw(img)

        cfg  = status.get("config", {})
        uart = status.get("uart", {})

        draw.text((4, 2), "SERVICES", font=self._font_hd, fill=(160, 160, 210))

        services = [
            ("WiFi Inhale",  True),          # always running if service is up
            ("BLE Inhale",   True),
            ("UART→ESP32",   uart.get("connected", False)),
            ("SSID Inject",  cfg.get("ssid_inject_enabled", False)),
            ("BLE Spoof",    cfg.get("ble_mac_spoof_enabled", False)),
            ("Mgmt AP",      cfg.get("mgmt_ap_enabled", False)),
        ]

        row_h = 11
        y = 18
        for label, active in services:
            dot = (0x44, 0xFF, 0x44) if active else (0x55, 0x55, 0x55)
            draw.ellipse([(4, y + 1), (10, y + 9)], fill=dot)
            text_col = (200, 200, 220) if active else (80, 80, 90)
            draw.text((14, y), label, font=self._font, fill=text_col)
            y += row_h

        return img


class RightPanel:
    """160×80 scrolling identifier ticker."""
    W, H = 160, 80
    MAX_LINES = 14       # line buffer depth

    def __init__(self):
        self._font   = _make_font(10)
        self._font_hd = _make_font(11)
        self._lines  = []
        self._lock   = threading.Lock()
        self._view   = 0   # 0=ticker, 1=BLE spoof status, 2=SSID inject status
        self._scroll = 0   # current scroll offset for ticker
        self._last_pool_total = 0

    def cycle_view(self):
        self._view = (self._view + 1) % 3

    def update_pool(self, status: dict):
        """Extract new identifiers and add to ticker."""
        cats = status.get("pool", {}).get("categories", {})
        total = status.get("pool", {}).get("total", 0)

        # Only update if pool grew
        if total <= self._last_pool_total:
            return
        self._last_pool_total = total

        # Pull samples from detail endpoint (best-effort)
        try:
            r = requests.get(f"{API_BASE}/api/pool/detail", timeout=2)
            if r.ok:
                detail = r.json()
                with self._lock:
                    for cat_key, label, color in CAT_CONFIG:
                        samples = detail.get(cat_key, [])
                        for s in samples[:2]:   # at most 2 per category per update
                            short = s[:22] if len(s) > 22 else s
                            self._lines.append((short, color))
                    # Cap buffer
                    if len(self._lines) > self.MAX_LINES:
                        self._lines = self._lines[-self.MAX_LINES:]
                    self._scroll = max(0, len(self._lines) - 6)
        except Exception:
            pass

    def render(self, status: dict) -> Image.Image:
        img  = Image.new("RGB", (self.W, self.H), (8, 8, 20))
        draw = ImageDraw.Draw(img)

        if self._view == 0:
            self._render_ticker(draw, status)
        elif self._view == 1:
            self._render_ble_spoof(draw, status)
        else:
            self._render_ssid_inject(draw, status)

        return img

    def _render_ticker(self, draw, status):
        draw.text((4, 2), "RECENT IDs", font=self._font_hd, fill=(160, 160, 210))
        with self._lock:
            visible = self._lines[self._scroll:self._scroll + 6]
        row_h = 11
        y = 15
        for text, color in visible:
            draw.text((4, y), text, font=self._font, fill=color)
            y += row_h
        # Scroll indicator
        if len(self._lines) > 6:
            pct = self._scroll / max(1, len(self._lines) - 6)
            bar_y = int(15 + pct * 55)
            draw.rectangle([(156, 15), (159, 70)], fill=(40, 40, 60))
            draw.rectangle([(156, bar_y), (159, bar_y + 8)], fill=(120, 120, 160))

    def tick_scroll(self):
        """Advance scroll position — called by ticker thread."""
        with self._lock:
            if len(self._lines) > 6:
                self._scroll = (self._scroll + 1) % max(1, len(self._lines) - 5)

    def _render_ble_spoof(self, draw, status):
        draw.text((4, 2), "BLE SPOOF", font=self._font_hd, fill=(0xC8, 0x4C, 0xFF))
        phase_b = status.get("phase_b", {})
        spoof = phase_b.get("ble_spoof", {})
        lines = [
            ("Active",   str(spoof.get("running", False))),
            ("MAC",      (spoof.get("current_mac") or "--")[:17]),
            ("Cycles",   str(spoof.get("cycle_count", 0))),
        ]
        y = 18
        for label, val in lines:
            draw.text((4, y),   label + ":", font=self._font, fill=(140, 140, 170))
            draw.text((60, y),  val,          font=self._font, fill=(220, 220, 240))
            y += 13

    def _render_ssid_inject(self, draw, status):
        draw.text((4, 2), "SSID INJECT", font=self._font_hd, fill=(0x4C, 0xFF, 0x9F))
        phase_b = status.get("phase_b", {})
        inj = phase_b.get("ssid_inject", {})
        ssid = (inj.get("last_ssid") or "--")[:18]
        lines = [
            ("Active",  str(inj.get("running", False))),
            ("SSID",    ssid),
            ("Beacons", str(inj.get("beacon_count", 0))),
        ]
        y = 18
        for label, val in lines:
            draw.text((4, y),   label + ":", font=self._font, fill=(140, 140, 170))
            draw.text((58, y),  val,          font=self._font, fill=(220, 220, 240))
            y += 13


# ── Display device setup ─────────────────────────────────────────
def _setup_displays():
    """Initialise luma.lcd display devices. Returns (center, left, right) or None."""
    if not LUMA_OK or not PIL_OK:
        return None, None, None
    try:
        # Center: ST7789 240×240 on CE0
        serial_center = spi(port=0, device=0, gpio_DC=24, gpio_RST=25,
                            bus_speed_hz=40000000)
        center = st7789(serial_center, width=240, height=240, rotate=0)

        # Left: ST7735S 160×80 on CE1 — adjust rotate/offset for your hat revision
        serial_left = spi(port=0, device=1, gpio_DC=24, gpio_RST=25,
                          bus_speed_hz=16000000)
        left = st7735(serial_left, width=160, height=80, rotate=2,
                      h_offset=1, v_offset=26)

        # Right: same SPI, different CS — many hat revisions share CE1 with a MUX
        # If your hat uses a dedicated CS for the right display, adjust device= here
        serial_right = spi(port=0, device=1, gpio_DC=24, gpio_RST=25,
                           bus_speed_hz=16000000)
        right = st7735(serial_right, width=160, height=80, rotate=0,
                       h_offset=1, v_offset=26)

        return center, left, right
    except Exception as e:
        log.error(f"Display init failed: {e}")
        return None, None, None


def _setup_gpio(right_panel: RightPanel):
    """Set up button GPIO."""
    if not GPIO_OK:
        return
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(KEY1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(KEY2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        def key1_callback(channel):
            log.info("Key1: triggering manual inhale")
            try:
                requests.post(f"{API_BASE}/api/action/inhale", timeout=3)
            except Exception:
                pass

        def key2_callback(channel):
            log.info("Key2: cycling right panel view")
            right_panel.cycle_view()

        GPIO.add_event_detect(KEY1_PIN, GPIO.FALLING, callback=key1_callback,
                              bouncetime=500)
        GPIO.add_event_detect(KEY2_PIN, GPIO.FALLING, callback=key2_callback,
                              bouncetime=300)
        log.info("GPIO buttons ready (Key1=inhale, Key2=cycle view)")
    except Exception as e:
        log.warning(f"GPIO setup failed: {e}")


# ── Main loop ────────────────────────────────────────────────────
def _fetch_status() -> dict:
    try:
        r = requests.get(f"{API_BASE}/api/status", timeout=3)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {}


def _display_image(device, img):
    """Push a PIL image to a luma device."""
    try:
        device.display(img)
    except Exception as e:
        log.debug(f"Display error: {e}")


def main():
    log.info("Antidote LCD service starting...")

    center_dev, left_dev, right_dev = _setup_displays()
    if not any([center_dev, left_dev, right_dev]):
        log.warning("No displays initialised — running in API-monitor-only mode")

    center_panel = CenterPanel()
    left_panel   = LeftPanel()
    right_panel  = RightPanel()

    _setup_gpio(right_panel)

    # Ticker scroll thread
    def _ticker():
        while True:
            right_panel.tick_scroll()
            time.sleep(TICKER_SPEED)

    threading.Thread(target=_ticker, daemon=True, name="ticker").start()

    log.info("LCD display loop running. Polling API every %ds", POLL_INTERVAL)

    last_status = {}
    while True:
        try:
            status = _fetch_status()
            if status:
                last_status = status
            else:
                status = last_status   # use cached on API error

            # Update right panel pool data
            right_panel.update_pool(status)

            # Render and push to displays
            if center_dev:
                _display_image(center_dev, center_panel.render(status))
            if left_dev:
                _display_image(left_dev,   left_panel.render(status))
            if right_dev:
                _display_image(right_dev,  right_panel.render(status))

            if not any([center_dev, left_dev, right_dev]):
                # Headless mode — just log what we'd show
                cats = status.get("pool", {}).get("categories", {})
                total = status.get("pool", {}).get("total", 0)
                log.info(f"Pool={total} | {cats} | mode={status.get('mode','?')}")

        except KeyboardInterrupt:
            log.info("Stopping.")
            if GPIO_OK:
                GPIO.cleanup()
            break
        except Exception as e:
            log.error(f"Loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
