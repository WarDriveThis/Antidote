#!/usr/bin/env python3
# main.py — Antidote Pi v1.9
#
# Thread layout:
#   Main thread     : inhale/exhale state machine + scheduling
#   Thread: web     : Flask server
#   Thread: uart    : Periodic UART push to ESP32-S3
#   Thread: ssid    : Continuous SSID beacon injection (wlan1mon)
#   Thread: ble-mac : BLE MAC cycling via nRF52840 dongle (hci0)
#
# Interface assignments:
#   wlan0 / wlan0mon  : capture (nexmon, persistent monitor)
#   wlan1 / wlan1mon  : SSID beacon injection (PAU0A #1, MT7610U)
#   wlan2             : management AP (PAU0A #2, MT7610U)
#   hci0              : BLE MAC spoofing (Laird BL654 dongle, USB)
#   /dev/serial0      : ESP32-S3 UART

import sys, os, time, threading, signal, gc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config           import Config
from logger           import Logger
from identifier_pool  import IdentifierPool
from wifi_inhale      import WifiInhaleEngine
from ble_inhale       import BleInhaleEngine
from uart_sync        import UartSync
from ssid_inject      import SsidInjector, SelfFilter
from ble_mac_spoof    import BleMacSpoofer
from hostapd_manager  import HostapdManager
from webserver        import create_app

# ------------------------------------------------------------------- Init

cfg  = Config()
log  = Logger()
pool = IdentifierPool(
    max_size        = cfg.get("max_pool_size", 2000),
    age_out_seconds = cfg.get("age_out_seconds", 7200),
)

action_queue = []

# Self-filter: BSSIDs we inject are skipped during capture
self_filter = SelfFilter()

wifi_eng    = WifiInhaleEngine(pool, cfg, log, self_filter=self_filter)
ble_eng     = BleInhaleEngine(pool, cfg, log)
uart_sync   = UartSync(pool, cfg, log)
ssid_inj    = SsidInjector(pool, cfg, log, self_filter)
ble_spoofer = BleMacSpoofer(pool, cfg, log)
ap_mgr      = HostapdManager(cfg, log)

# ----------------------------------------------------------- Web server

flask_app = create_app(cfg, pool, log, uart_sync, action_queue, ble_spoofer, ssid_inj)

def _run_web():
    host = cfg.get("web_host", "0.0.0.0")
    port = cfg.get("web_port", 5000)
    log.info(f"[WEB] Starting on http://{host}:{port}")
    flask_app.run(host=host, port=port, debug=False, use_reloader=False)

threading.Thread(target=_run_web, daemon=True, name="web").start()

# ---------------------------------------------------------------- Shutdown

_shutdown = threading.Event()

def _handle_signal(signum, frame):
    log.info(f"Signal {signum} — shutting down.")
    _shutdown.set()

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# -------------------------------------------------------------- State machine

MODE_IDLE   = "IDLE"
MODE_INHALE = "INHALE"
MODE_ERROR  = "ERROR"
current_mode = MODE_IDLE

def set_mode(m):
    global current_mode
    current_mode = m
    # Keep action_queue[0] updated as mode indicator for web UI
    if action_queue and action_queue[0] in (MODE_IDLE, MODE_INHALE, MODE_ERROR):
        action_queue[0] = m
    else:
        action_queue.insert(0, m)

def do_inhale():
    set_mode(MODE_INHALE)
    log.info("=== Inhale cycle start ===")
    stop_evt    = threading.Event()
    wifi_result = wifi_eng.run_cycle(stop_event=stop_evt)
    ble_result  = ble_eng.run_cycle()
    stats = pool.stats()
    log.info(
        f"Inhale complete. Pool={stats['total']} | "
        f"WiFi frames={wifi_result.get('frames', 0)} | "
        f"BLE={ble_result.get('devices', 0)}"
    )
    uart_sync.push_sample()
    set_mode(MODE_IDLE)
    gc.collect()
    return stats

# ---------------------------------------------------------------- Boot

log.info("Antidote Pi v1.9 starting.")
log.info(f"Pool: max={cfg.get('max_pool_size')} age_out={cfg.get('age_out_seconds')}s")

# One-time capture monitor interface setup (wlan0mon)
wifi_eng.setup_service()

# UART sync to ESP32
uart_sync.start()

# Phase B engines — each checks its own enabled flag before starting
ssid_inj.start()
ble_spoofer.start()
ap_mgr.start()

# Startup inhale
log.info("Running startup inhale...")
do_inhale()
last_inhale_time = time.time()
log.info("Entering operational loop.")

# ---------------------------------------------------------------- Main loop

while not _shutdown.is_set():
    now = time.time()

    # Process commands queued by web UI (filter out mode strings)
    cmds = [a for a in action_queue
            if a not in (MODE_IDLE, MODE_INHALE, MODE_ERROR)]
    for cmd in cmds:
        action_queue.remove(cmd)
        if cmd == "inhale":
            log.info("Manual inhale triggered from web UI.")
            do_inhale()
            last_inhale_time = time.time()
        elif cmd == "restart_ap":
            log.info("Restarting management AP.")
            ap_mgr.stop()
            time.sleep(1)
            ap_mgr.start()
        elif cmd == "stop_ap":
            log.info("Stopping management AP.")
            ap_mgr.stop()
        elif cmd == "start_ssid":
            log.info("Starting SSID injection.")
            ssid_inj.start()
        elif cmd == "stop_ssid":
            log.info("Stopping SSID injection.")
            ssid_inj.stop()
        elif cmd == "start_ble_spoof":
            log.info("Starting BLE MAC spoofing.")
            ble_spoofer.start()
        elif cmd == "stop_ble_spoof":
            log.info("Stopping BLE MAC spoofing.")
            ble_spoofer.stop()

    # Scheduled inhale
    freq = cfg.get("inhale_frequency", 300)
    if freq == 0:
        do_inhale()
        last_inhale_time = time.time()
    elif (now - last_inhale_time) >= freq:
        log.info(f"Scheduled inhale (every {freq}s).")
        do_inhale()
        last_inhale_time = time.time()

    time.sleep(1)

# ---------------------------------------------------------------- Cleanup

log.info("Shutting down.")
ssid_inj.stop()
ble_spoofer.stop()
ap_mgr.stop()
uart_sync.stop()
wifi_eng.teardown_service()
sys.exit(0)
