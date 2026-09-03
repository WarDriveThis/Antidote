# main.py - Antidote ESP32-S3 v1.9
# No WiFi AP, no web server. Radio dedicated to BLE.
# Thread 0: inhale / exhale state machine
# Thread 1: UART receive from Pi

import time
import gc
import _thread

from config          import Config
from hardware        import Hardware
from logger          import Logger
from identifier_pool import IdentifierPool
from inhale          import InhaleEngine
from exhale          import ExhaleEngine
from uart_receive    import UartReceive

cfg  = Config()
log  = Logger()
hw   = Hardware()
pool = IdentifierPool(
    max_size        = cfg.get("max_pool_size", 500),
    age_out_seconds = cfg.get("age_out_seconds", 3600)
)

inhale_eng = InhaleEngine(pool, cfg, hw)
exhale_eng = ExhaleEngine(pool, cfg, hw)
uart_rx    = UartReceive(pool, cfg, log, hw)

hw.startup_tone()
log.info("Antidote v1.9 boot complete.")
log.info("Free memory: {} bytes".format(gc.mem_free()))
gc.collect()

def _uart_thread():
    uart_rx.run()

_thread.start_new_thread(_uart_thread, ())
log.info("UART receive thread started.")

MODE_IDLE   = "IDLE"
MODE_INHALE = "INHALE"
MODE_EXHALE = "EXHALE"
current_mode = MODE_IDLE

def set_mode(mode):
    global current_mode
    current_mode = mode
    log.info("Mode -> {}".format(mode))

def do_inhale():
    set_mode(MODE_INHALE)
    hw.stop_pulse()          # Stop idle white pulse before inhale
    time.sleep_ms(60)        # Let pulse thread exit cleanly
    try:
        stats = inhale_eng.run_cycle()
        log.info("Inhale complete. Pool={} IDs".format(stats['total']))
    except Exception as e:
        log.error("Inhale error: {}".format(e))
        hw.error_tone()
    finally:
        set_mode(MODE_IDLE)
        hw.stop_pulse()

def do_exhale():
    set_mode(MODE_EXHALE)
    try:
        result = exhale_eng.run_cycle()
        log.info("Exhale complete. Broadcast={} payloads, Pool={} IDs".format(
            result['broadcasted'], result['pool_size']))
    except Exception as e:
        log.error("Exhale error: {}".format(e))
        hw.error_tone()
    finally:
        set_mode(MODE_IDLE)
        hw.stop_pulse()

log.info("Starting initial inhale cycle...")
do_inhale()

last_inhale_time = time.time()
last_exhale_time = time.time()

log.info("Entering operational loop.")
hw.pulse(hw.COLOR_WHITE)

while True:
    now = time.time()

    inhale_freq = cfg.get("inhale_frequency", 300)
    if inhale_freq > 0 and (now - last_inhale_time) >= inhale_freq:
        log.info("Scheduled inhale (every {}s).".format(inhale_freq))
        do_inhale()
        last_inhale_time = time.time()
    elif inhale_freq == 0:
        do_inhale()
        last_inhale_time = time.time()

    exhale_interval = cfg.get("exhale_interval", 10)  # v1.9: was 30
    if pool.count() > 0 and (now - last_exhale_time) >= exhale_interval:
        log.info("Scheduled exhale (every {}s).".format(exhale_interval))
        do_exhale()
        last_exhale_time = time.time()

    if current_mode == MODE_IDLE and not hw._pulse_active:
        hw.pulse(hw.COLOR_WHITE)

    gc.collect()
    time.sleep_ms(1000)
