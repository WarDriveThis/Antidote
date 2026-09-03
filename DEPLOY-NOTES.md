# Antidote v1.9 Deploy Notes

## Pi deploy (3 steps)

### Step 1 — copy source files
```bash
scp pi/src/*.py kali@<Pi-IP>:~/antidote/src/
```

### Step 2 — restart Antidote
```bash
sudo systemctl restart antidote.service
journalctl -u antidote.service -f
# Look for: Antidote Pi v1.9 starting.
```

### Step 3 — clear saved config so new defaults take effect
The saved config at /home/kali/.antidote/config.json overrides defaults.
Either clear it (service recreates on next save):
```bash
sudo rm /home/kali/.antidote/config.json
sudo systemctl restart antidote.service
```
Or update individual keys manually:
```bash
sudo python3 -c "
import json
with open('/home/kali/.antidote/config.json') as f: c=json.load(f)
c.update({'uart_sync_interval':15,'ssid_inject_rate':20,
          'ble_mac_spoof_interval':8,
          'ssid_inject_channels':[1,6,11,36,40,44,48,149,165]})
with open('/home/kali/.antidote/config.json','w') as f: json.dump(c,f,indent=2)
print('Config updated')
"
sudo systemctl restart antidote.service
```

---

## ESP32 deploy

### main.py — exhale interval default changed (10s was 30s)
```
py -m mpremote connect COM18 cp esp32/main.py :main.py
py -m mpremote connect COM18 reset
```

### exhale.py — patch payloads per cycle (10 → 25)
The exhale.py lives only on the device. Run the included patch script:
```
py -m mpremote connect COM18 run esp32/patch_exhale.py
py -m mpremote connect COM18 reset
```
If patch_exhale.py reports it couldn't auto-patch, paste the output
here and a targeted replacement will be provided.

---

## LCD display service (new in v1.9)

### Install Python dependencies (on Pi)
```bash
/home/kali/antidote-env/bin/pip install luma.lcd luma.core pillow requests
```

### Enable SPI on the Pi (if not already done)
```bash
sudo raspi-config  # → Interface Options → SPI → Enable
# or add dtparam=spi=on to /boot/firmware/config.txt
sudo reboot
```

### Deploy and start
```bash
scp pi/src/lcd_display.py kali@<Pi-IP>:~/antidote/src/
scp antidote-lcd.service kali@<Pi-IP>:~/
sudo cp ~/antidote-lcd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable antidote-lcd.service
sudo systemctl start antidote-lcd.service
journalctl -u antidote-lcd.service -f
```

### Test without displays (headless API monitor mode)
The service runs headlessly if luma.lcd is not installed or displays
fail to init — it logs pool status every 3 seconds instead.
Use this to verify the API integration before connecting hardware:
```bash
/home/kali/antidote-env/bin/python /home/kali/antidote/src/lcd_display.py
```

### Waveshare Zero LCD Hat (A) SPI wiring — verified no GPIO conflicts
```
SPI MOSI: GPIO10    SPI CLK: GPIO11
CE0: GPIO8  (center 240×240 display)
CE1: GPIO7  (side 160×80 displays — check your hat revision)
DC:  GPIO24          RST: GPIO25
BL:  GPIO13 (backlight — VERIFY against your specific hat revision)
Key1: GPIO21  →  triggers manual inhale via /api/action/inhale
Key2: GPIO20  →  cycles right panel view (ticker / BLE spoof / SSID inject)
ANTIDOTE UART: GPIO14 (TX), GPIO15 (RX) — NO CONFLICT
```

### Display layout
```
┌─────────────────┬──────────────┬──────────────┐
│  LEFT 160×80    │ CENTER 240×240│  RIGHT 160×80 │
│  Service Health │ Pool Dashboard│  ID Ticker   │
│                 │               │  (Key2 cycles)│
│  ● WiFi Inhale  │  Probes:  42  │  aa:bb:cc:... │
│  ● BLE Inhale   │  SSIDs:    8  │  HomeNetwork  │
│  ● UART→ESP32   │  BSSIDs:  19  │  de:ad:be:... │
│  ○ SSID Inject  │  Clients:  3  │  Ember Ceramic│
│  ○ BLE Spoof    │  BLE MACs: 11 │  ...          │
│  ○ Mgmt AP      │  BLE Names: 6 │               │
│                 │  Manuf:    4  │               │
│                 │               │               │
│                 │ Pool:62  IDLE │               │
└─────────────────┴───────────────┴───────────────┘
```
Dot colours: green = active, grey = disabled.
Count colours: blue=WiFi, green=SSID/BSSID, amber=clients, purple=BLE.
Freshness dot (right of each count): green=<5min, amber=<15min, red=stale.
