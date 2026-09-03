# webserver.py — Antidote Pi Flask management interface v1.9
#
# v1.6 changes:
#   - Header redesign: Son of Man image, vertical title, enlarged test tube
#   - Subtitle changed to "Privacy Enhancement System – v1.6"
#   - wlan0 as default for Management AP
#   - Pool snapshot buttons per category (full pool, one-shot, not live)
#   - Last ID sent display per Phase B feature (optional checkbox)
#   - /api/pool/full endpoint (entire pool by category)
#   - /api/phase_b_status endpoint (current_mac, cycle_count, last_ssid)
#   - Version bump throughout

from flask import Flask, request, jsonify, make_response, render_template_string
import time

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Antidote v1.9</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:#0a0a14;color:#e0e0e0;min-height:100vh;padding:24px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
        gap:16px;max-width:1280px;margin:0 auto}
  /* ── Header ── */
  .header-bar{display:flex;align-items:center;justify-content:center;
              gap:18px;margin-bottom:6px}
  .header-title-vert{writing-mode:vertical-rl;text-orientation:upright;
                     letter-spacing:4px;font-size:1.5rem;font-weight:900;
                     color:#4ade80;line-height:1;user-select:none}
  .header-som{width:160px;height:160px;object-fit:cover;border-radius:8px;
              border:1px solid #1e1e35;flex-shrink:0}
  .header-tube{font-size:6.5rem;line-height:1;flex-shrink:0}
  .tagline{color:#555;text-align:center;font-size:0.82rem;margin-bottom:24px}
  /* ── Cards ── */
  .card{background:#12121f;border:1px solid #1e1e35;border-radius:12px;padding:20px}
  h2{color:#a78bfa;font-size:0.88rem;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:14px}
  label{display:block;font-size:0.8rem;color:#888;margin-bottom:4px;margin-top:10px}
  input[type=text],input[type=number],input[type=password],select{
    width:100%;padding:8px 10px;background:#0a0a14;border:1px solid #2a2a45;
    border-radius:6px;color:#e0e0e0;font-size:0.88rem}
  input[readonly]{color:#555;cursor:default}
  input:focus,select:focus{outline:none;border-color:#4ade80}
  .check-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:0.85rem;color:#ccc}
  input[type=checkbox]{accent-color:#4ade80;width:15px;height:15px}
  .stat-row{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
  .stat{background:#0a0a14;border-radius:6px;padding:10px;text-align:center;position:relative}
  .sv{font-size:1.4rem;font-weight:700}
  .sv-fresh{color:#4ade80}.sv-warm{color:#86efac}.sv-stale{color:#facc15}
  .sv-old{color:#f87171}.sv-unknown{color:#555}
  .sl{font-size:0.68rem;color:#666;margin-top:2px}
  .fd{width:6px;height:6px;border-radius:50%;position:absolute;top:6px;right:6px}
  .fd-fresh{background:#4ade80}.fd-warm{background:#86efac}.fd-stale{background:#facc15}
  .fd-old{background:#f87171}.fd-unknown{background:#333}
  .badge{display:inline-block;padding:3px 12px;border-radius:20px;font-size:0.78rem;font-weight:700;letter-spacing:1px}
  .b-inhale{background:#14532d;color:#4ade80}.b-exhale{background:#422006;color:#fb923c}
  .b-idle{background:#1e1b4b;color:#818cf8}.b-error{background:#450a0a;color:#f87171}
  .btn{display:block;width:100%;padding:11px;border:none;border-radius:8px;
       font-size:0.88rem;font-weight:700;cursor:pointer;margin-top:8px;letter-spacing:1px}
  .btn-p{background:#4ade80;color:#0a0a14}.btn-p:hover{opacity:.85}
  .btn-o{background:transparent;border:1px solid #4ade80;color:#4ade80}.btn-o:hover{opacity:.75}
  .btn-d{background:#ef4444;color:#fff}.btn-d:hover{opacity:.85}
  .btn-y{background:#f59e0b;color:#0a0a14}.btn-y:hover{opacity:.85}
  .btn-b{background:#3b82f6;color:#fff}.btn-b:hover{opacity:.85}
  .btn-sm{display:inline-block;width:auto;padding:3px 10px;font-size:0.72rem;
          margin:0 0 0 8px;vertical-align:middle;letter-spacing:0.5px}
  .log{background:#050510;border:1px solid #1a1a30;border-radius:6px;padding:10px;
       font-family:monospace;font-size:0.73rem;color:#34d399;max-height:200px;
       overflow-y:auto;white-space:pre-wrap;line-height:1.5}
  .uart-row{display:flex;align-items:center;gap:8px;margin-top:8px}
  .dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
  .dot-on{background:#4ade80}.dot-off{background:#ef4444}
  #toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
         padding:10px 24px;border-radius:8px;font-weight:700;display:none;z-index:999}
  .uptime{font-size:0.75rem;color:#555;text-align:center;margin-top:16px}
  .ro-badge{font-size:0.68rem;color:#555;margin-left:6px}
  .section-note{font-size:0.72rem;color:#555;margin-top:6px;font-style:italic}
  /* ── Pool detail / snapshot ── */
  .detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin-top:12px}
  .detail-card{background:#0a0a14;border:1px solid #1e1e35;border-radius:8px;padding:12px}
  .detail-cat{font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;color:#a78bfa;
              margin-bottom:8px;display:flex;align-items:center;justify-content:space-between}
  .detail-val{font-family:monospace;font-size:0.72rem;color:#86efac;padding:3px 0;
              border-bottom:1px solid #0d0d20;word-break:break-all}
  .detail-val:last-child{border-bottom:none}
  .detail-empty{font-size:0.72rem;color:#333;font-style:italic}
  #detailSection{display:none;margin-top:12px;border-top:1px solid #1e1e35;padding-top:12px}
  /* ── Snapshot modal ── */
  #snapModal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:500;
             overflow-y:auto;padding:24px}
  #snapInner{background:#12121f;border:1px solid #1e1e35;border-radius:12px;
             max-width:680px;margin:0 auto;padding:20px}
  #snapTitle{color:#a78bfa;font-size:0.9rem;text-transform:uppercase;
             letter-spacing:1.5px;margin-bottom:12px}
  #snapList{font-family:monospace;font-size:0.76rem;color:#86efac;
            white-space:pre-wrap;max-height:60vh;overflow-y:auto;
            background:#050510;border:1px solid #1a1a30;border-radius:6px;padding:10px}
  #snapNote{font-size:0.7rem;color:#555;margin-top:8px;font-style:italic}
  /* ── Last ID sent ── */
  .last-id-row{display:flex;align-items:center;gap:8px;margin-top:10px;
               flex-wrap:wrap}
  .last-id-label{font-size:0.72rem;color:#555;flex-shrink:0}
  .last-id-val{font-family:monospace;font-size:0.8rem;color:#fbbf24;
               background:#0a0a14;border:1px solid #2a2a45;border-radius:4px;
               padding:3px 8px;flex:1;min-width:0;overflow:hidden;
               text-overflow:ellipsis;white-space:nowrap}
  .last-id-cycle{font-size:0.68rem;color:#555;flex-shrink:0}
  /* ── Phase badge ── */
  .phase-badge{font-size:0.68rem;background:#1e1b4b;color:#818cf8;
               padding:2px 7px;border-radius:10px;margin-left:6px;vertical-align:middle}
</style>
</head>
<body>

<!-- Header -->
<div class="header-bar">
  <span class="header-title-vert">ANTIDOTE</span>
  <img class="header-som" src="data:image/jpeg;base64,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" alt="Son of Man">
  <span class="header-tube">&#x1F9EA;</span>
</div>
<p class="tagline">Privacy Enhancement System &ndash; v1.9</p>

<div class="grid">

  <!-- Status -->
  <div class="card">
    <h2>System Status</h2>
    <p>Mode: <span class="badge b-idle" id="modeLabel">LOADING</span></p>
    <div class="stat-row" style="margin-top:14px">
      <div class="stat"><div class="fd fd-unknown" id="fd_total"></div><div class="sv sv-unknown" id="sTotal">--</div><div class="sl">Total IDs</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_probe"></div><div class="sv sv-unknown" id="sProbe">--</div><div class="sl">WiFi Probes</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_ble_mac"></div><div class="sv sv-unknown" id="sBLE">--</div><div class="sl">BLE MACs</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_ble_uuid"></div><div class="sv sv-unknown" id="sUUID">--</div><div class="sl">UUIDs</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_ssid"></div><div class="sv sv-unknown" id="sSSID">--</div><div class="sl">SSIDs</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_bssid"></div><div class="sv sv-unknown" id="sBSSID">--</div><div class="sl">BSSIDs</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_client"></div><div class="sv sv-unknown" id="sClient">--</div><div class="sl">Client MACs</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_manuf"></div><div class="sv sv-unknown" id="sManuf">--</div><div class="sl">Manuf IDs</div></div>
      <div class="stat"><div class="fd fd-unknown" id="fd_ble_name"></div><div class="sv sv-unknown" id="sBLEName">--</div><div class="sl">BLE Names</div></div>
    </div>
    <div class="uart-row" style="margin-top:14px">
      <div class="dot dot-off" id="uartDot"></div>
      <span id="uartStatus" style="font-size:0.8rem;color:#888">ESP32 UART: checking...</span>
    </div>
    <!-- Pool sample toggle -->
    <div class="check-row" style="margin-top:12px">
      <input type="checkbox" id="showDetail" onchange="toggleDetail()">
      <label style="margin:0;color:#888;cursor:pointer" for="showDetail">Show pool sample (5 per category)</label>
    </div>
    <div id="detailSection">
      <div class="detail-grid" id="detailGrid"></div>
    </div>
  </div>

  <!-- Collection Config -->
  <div class="card">
    <h2>Collection (Inhale)</h2>
    <label>Duration (sec, 0=continuous)</label>
    <input type="number" id="inhale_duration" min="0" max="3600">
    <label>Frequency (sec between cycles)</label>
    <input type="number" id="inhale_frequency" min="10" max="86400">
    <p style="font-size:0.8rem;color:#666;margin-top:12px;margin-bottom:4px">Collect:</p>
    <div class="check-row"><input type="checkbox" id="collect_ble_mac"> BLE MAC Addresses</div>
    <div class="check-row"><input type="checkbox" id="collect_ble_uuid"> BLE Service UUIDs</div>
    <div class="check-row"><input type="checkbox" id="collect_ble_name"> BLE Device Names</div>
    <div class="check-row"><input type="checkbox" id="collect_ble_manuf"> BLE Manufacturer Data</div>
    <div class="check-row"><input type="checkbox" id="collect_wifi_probe"> WiFi Probe Requests</div>
    <div class="check-row"><input type="checkbox" id="collect_wifi_beacon"> WiFi Beacons / SSIDs</div>
    <div class="check-row"><input type="checkbox" id="collect_wifi_assoc"> WiFi Association Requests <span style="color:#888;font-size:0.8rem">(client MACs joining nearby APs)</span></div>
    <div class="check-row"><input type="checkbox" id="collect_wifi_deauth"> WiFi Deauth Frames <span style="color:#888;font-size:0.8rem">(client MACs on disconnect)</span></div>
    <label>WiFi Capture Interface</label>
    <input type="text" id="wifi_interface">
    <label>Monitor Mode <span class="ro-badge">read-only</span></label>
    <input type="text" id="wifi_use_airmon_display" readonly>
    <label>WiFi Starting Channel (1-13)</label>
    <input type="number" id="wifi_channel" min="1" max="13">
  </div>

  <!-- Pool Config -->
  <div class="card">
    <h2>Pool Settings</h2>
    <label>Max Pool Size</label>
    <input type="number" id="max_pool_size" min="100" max="10000">
    <label>Pool Retention (hours)</label>
    <input type="number" id="pool_retention_hours" min="1" max="24">
    <p class="section-note">Identifiers not seen within this window are removed from the pool.</p>
    <label>Exhale / UART Sync Interval (sec)</label>
    <input type="number" id="exhale_interval" min="5" max="3600">
  </div>

  <!-- UART Sync -->
  <div class="card">
    <h2>ESP32-S3 UART Sync</h2>
    <label>Serial Port</label>
    <input type="text" id="uart_port">
    <label>Baud Rate</label>
    <select id="uart_baud">
      <option value="9600">9600</option>
      <option value="57600">57600</option>
      <option value="115200">115200 (recommended)</option>
      <option value="230400">230400</option>
    </select>
    <label>Sync Interval (sec)</label>
    <input type="number" id="uart_sync_interval" min="5" max="300">
    <label>Sample Size (IDs per push)</label>
    <input type="number" id="uart_sample_size" min="5" max="200">
  </div>

  <!-- SSID Injection -->
  <div class="card">
    <h2>SSID Injection <span class="phase-badge">Phase B</span></h2>
    <div class="check-row"><input type="checkbox" id="ssid_inject_enabled"> Enable beacon injection</div>
    <label>Inject Interface (wlan2)</label>
    <input type="text" id="ssid_inject_interface">
    <label>Beacons per second per SSID</label>
    <input type="number" id="ssid_inject_rate" min="1" max="50">
    <p class="section-note">Injects beacon frames for each SSID in the pool on wlan2. Own BSSIDs are filtered from capture.</p>
    <!-- Last ID sent -->
    <div class="check-row" style="margin-top:12px">
      <input type="checkbox" id="show_last_ssid" onchange="toggleLastID()">
      <label style="margin:0;color:#666;cursor:pointer;font-size:0.75rem" for="show_last_ssid">Show last injected SSID</label>
    </div>
    <div id="lastSsidRow" style="display:none">
      <div class="last-id-row">
        <span class="last-id-label">Last SSID:</span>
        <span class="last-id-val" id="lastSsidVal">—</span>
        <span class="last-id-cycle" id="lastSsidCycle"></span>
      </div>
      <div class="last-id-row" style="margin-top:4px">
        <span class="last-id-label">BSSID:</span>
        <span class="last-id-val" id="lastBssidVal">—</span>
      </div>
    </div>
  </div>

  <!-- BLE MAC Spoof -->
  <div class="card">
    <h2>BLE MAC Spoofing <span class="phase-badge">Phase B</span></h2>
    <div class="check-row"><input type="checkbox" id="ble_mac_spoof_enabled"> Enable MAC spoofing</div>
    <label>HCI Interface (nRF52840)</label>
    <input type="text" id="ble_mac_spoof_interface">
    <label>MAC cycle interval (sec)</label>
    <input type="number" id="ble_mac_spoof_interval" min="5" max="300">
    <p class="section-note">Requires nRF52840 on USB and Pi built-in BT disabled (dtoverlay=disable-bt in /boot/config.txt).</p>
    <!-- Last ID sent -->
    <div class="check-row" style="margin-top:12px">
      <input type="checkbox" id="show_last_mac" onchange="toggleLastID()">
      <label style="margin:0;color:#666;cursor:pointer;font-size:0.75rem" for="show_last_mac">Show last broadcast MAC</label>
    </div>
    <div id="lastMacRow" style="display:none">
      <div class="last-id-row">
        <span class="last-id-label">Broadcasting as:</span>
        <span class="last-id-val" id="lastMacVal">—</span>
        <span class="last-id-cycle" id="lastMacCycle"></span>
      </div>
      <div class="last-id-row" style="margin-top:4px">
        <span class="last-id-label">HCI confirm:</span>
        <span class="last-id-val" id="lastMacOs">—</span>
      </div>
    </div>
  </div>

  <!-- Management AP -->
  <div class="card">
    <h2>Management AP <span class="phase-badge">Phase B</span></h2>
    <div class="check-row"><input type="checkbox" id="mgmt_ap_enabled"> Enable AP</div>
    <label>AP Interface (wlan0)</label>
    <input type="text" id="mgmt_ap_interface">
    <label>AP SSID (broadcast name)</label>
    <input type="text" id="mgmt_ap_ssid" maxlength="32">
    <label>Change AP Password (optional, min 8 chars)</label>
    <input type="password" id="mgmt_ap_password" minlength="8" autocomplete="new-password" placeholder="Leave blank to keep current">
    <label>Channel</label>
    <input type="number" id="mgmt_ap_channel" min="1" max="11">
    <p class="section-note">Web UI accessible at http://192.168.4.1:5000 when connected to this AP. Uses wlan0 (Pi built-in) — dedicated, no conflict with injection. Password field only needed when changing the password — leave blank to keep current.</p>
    <button class="btn btn-b" style="margin-top:10px" onclick="restartAP()">&#x21BB; Restart AP</button>
  </div>

  <!-- Actions -->
  <div class="card">
    <h2>Actions</h2>
    <button class="btn btn-p" onclick="saveConfig()">Save &amp; Apply Config</button>
    <button class="btn btn-o" style="margin-top:10px" onclick="forceInhale()">&#x1F4E5; Force Inhale Cycle</button>
    <button class="btn btn-y" style="margin-top:10px" onclick="forceUartPush()">&#x1F4E4; Force UART Push to ESP32</button>
    <button class="btn btn-d" style="margin-top:10px" onclick="resetConfig()">Reset to Defaults</button>
  </div>

  <!-- ESP32-S3 Status (read-only) -->
  <div class="card">
    <h2>ESP32-S3 Status</h2>
    <p style="color:#888;font-size:0.85rem;margin-bottom:10px">
      Read-only view of what the Pi knows about the ESP32-S3.
      The ESP32 runs independently — these values reflect Pi-side tracking only.
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:0.9rem">
      <tr><td style="color:#888;padding:4px 0">UART link</td>
          <td id="esp32_link" style="font-weight:600">--</td></tr>
      <tr><td style="color:#888;padding:4px 0">Total pushes sent</td>
          <td id="esp32_pushes">--</td></tr>
      <tr><td style="color:#888;padding:4px 0">Last push at</td>
          <td id="esp32_last_push">--</td></tr>
      <tr><td style="color:#888;padding:4px 0">Last push error</td>
          <td id="esp32_error" style="color:#e07">--</td></tr>
      <tr><td style="color:#888;padding:4px 0">Identifiers in last push</td>
          <td id="esp32_sample_size">--</td></tr>
      <tr><td style="color:#888;padding:4px 0">NeoPixel</td>
          <td style="color:#888;font-size:0.8rem">Green flash = receiving from Pi &nbsp;|&nbsp; Yellow = exhaling &nbsp;|&nbsp; Blue = BLE inhale &nbsp;|&nbsp; White = idle</td></tr>
    </table>
  </div>

  <!-- Log -->
  <div class="card" style="grid-column: 1 / -1">
    <h2>Device Log <span style="float:right;font-size:0.75rem;color:#555;cursor:pointer" onclick="clearLog()">clear</span></h2>
    <div class="log" id="logBox">Loading...</div>
  </div>

</div>
<p class="uptime" id="uptime"></p>
<div id="toast"></div>

<!-- Pool snapshot modal -->
<div id="snapModal" onclick="closeSnap(event)">
  <div id="snapInner">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <span id="snapTitle">Pool Snapshot</span>
      <button class="btn btn-o" style="width:auto;padding:4px 14px;margin:0;font-size:0.78rem"
              onclick="document.getElementById('snapModal').style.display='none'">Close</button>
    </div>
    <div id="snapList"></div>
    <p id="snapNote">Snapshot taken at <span id="snapTime"></span> — not live</p>
  </div>
</div>

<script>
var $ = function(id){return document.getElementById(id);};
var _detailVisible = false;
var _showLastMac   = false;
var _showLastSsid  = false;

function toast(msg, ok){
  if(ok===undefined) ok=true;
  var t=$('toast');
  t.textContent=msg;
  t.style.background=ok?'#4ade80':'#ef4444';
  t.style.color=ok?'#0a0a14':'#fff';
  t.style.display='block';
  setTimeout(function(){t.style.display='none';},2800);
}

function freshnessClass(secs){
  if(secs===null||secs===undefined) return 'unknown';
  if(secs<300)  return 'fresh';
  if(secs<900)  return 'warm';
  if(secs<3600) return 'stale';
  return 'old';
}

function setCell(svId, dotId, value, freshSecs){
  var cls=freshnessClass(freshSecs);
  $(svId).textContent=(value!==null&&value!==undefined)?value:'--';
  $(svId).className='sv sv-'+cls;
  $(dotId).className='fd fd-'+cls;
}

function toggleLastID(){
  _showLastMac  = $('show_last_mac').checked;
  _showLastSsid = $('show_last_ssid').checked;
  $('lastMacRow').style.display  = _showLastMac  ? 'block' : 'none';
  $('lastSsidRow').style.display = _showLastSsid ? 'block' : 'none';
}

async function loadPhaseBStatus(){
  if(!_showLastMac && !_showLastSsid) return;
  try{
    var r=await fetch('/api/phase_b_status');
    var d=await r.json();
    if(_showLastMac){
      $('lastMacVal').textContent   = d.current_mac  || '—';
      $('lastMacCycle').textContent = d.mac_cycle_count ? 'cycle #'+d.mac_cycle_count : '';
      $('lastMacOs').textContent    = d.os_mac || '—';
    }
    if(_showLastSsid){
      $('lastSsidVal').textContent  = d.last_ssid  || '—';
      $('lastBssidVal').textContent = d.last_bssid || '—';
      $('lastSsidCycle').textContent= d.ssid_beacon_count ? d.ssid_beacon_count+' beacons' : '';
    }
  }catch(e){}
}

async function loadStatus(){
  try{
    var r=await fetch('/api/status');
    var d=await r.json();
    var cfg=d.config||{};
    var pool=d.pool||{};
    var cats=pool.categories||{};
    var fresh=pool.freshness||{};
    var uart=d.uart||{};

    // Collection fields
    $('inhale_duration').value=cfg.inhale_duration||60;
    $('inhale_frequency').value=cfg.inhale_frequency||300;
    $('collect_ble_mac').checked=!!cfg.collect_ble_mac;
    $('collect_ble_uuid').checked=!!cfg.collect_ble_uuid;
    $('collect_ble_name').checked=!!cfg.collect_ble_name;
    $('collect_ble_manuf').checked=!!cfg.collect_ble_manuf;
    $('collect_wifi_probe').checked=!!cfg.collect_wifi_probe;
    $('collect_wifi_beacon').checked=!!cfg.collect_wifi_beacon;
    $('collect_wifi_assoc').checked=(cfg.collect_wifi_assoc!==false);
    $('collect_wifi_deauth').checked=(cfg.collect_wifi_deauth!==false);
    $('wifi_interface').value=cfg.wifi_interface||'wlan1';
    $('wifi_use_airmon_display').value=cfg.wifi_use_airmon?'Enabled (Kali/nexmon)':'Disabled';
    $('wifi_channel').value=cfg.wifi_channel||6;

    // Pool
    $('max_pool_size').value=cfg.max_pool_size||2000;
    $('pool_retention_hours').value=cfg.pool_retention_hours||2;
    $('exhale_interval').value=cfg.exhale_interval||30;

    // UART
    $('uart_port').value=cfg.uart_port||'/dev/serial0';
    $('uart_baud').value=String(cfg.uart_baud||115200);
    $('uart_sync_interval').value=cfg.uart_sync_interval||15;
    $('uart_sample_size').value=cfg.uart_sample_size||50;

    // Phase B
    $('ssid_inject_enabled').checked=!!cfg.ssid_inject_enabled;
    $('ssid_inject_interface').value=cfg.ssid_inject_interface||'wlan2';
    $('ssid_inject_rate').value=cfg.ssid_inject_rate||20;
    $('ble_mac_spoof_enabled').checked=!!cfg.ble_mac_spoof_enabled;
    $('ble_mac_spoof_interface').value=cfg.ble_mac_spoof_interface||'hci0';
    $('ble_mac_spoof_interval').value=cfg.ble_mac_spoof_interval||8;
    $('mgmt_ap_enabled').checked=!!cfg.mgmt_ap_enabled;
    $('mgmt_ap_interface').value=cfg.mgmt_ap_interface||'wlan0';
    $('mgmt_ap_ssid').value=cfg.mgmt_ap_ssid||'Antidote';
    $('mgmt_ap_channel').value=cfg.mgmt_ap_channel||1;

    // Stats
    setCell('sTotal',   'fd_total',    pool.total,             null);
    setCell('sProbe',   'fd_probe',    cats.wifi_probe_mac,    fresh.wifi_probe_mac);
    setCell('sBLE',     'fd_ble_mac',  cats.ble_mac,           fresh.ble_mac);
    setCell('sUUID',    'fd_ble_uuid', cats.ble_uuid,          fresh.ble_uuid);
    setCell('sSSID',    'fd_ssid',     cats.wifi_ssid,         fresh.wifi_ssid);
    setCell('sBSSID',   'fd_bssid',    cats.wifi_bssid,        fresh.wifi_bssid);
    setCell('sClient',  'fd_client',   cats.wifi_client_mac,   fresh.wifi_client_mac);
    setCell('sManuf',   'fd_manuf',    cats.ble_manuf,         fresh.ble_manuf);
    setCell('sBLEName', 'fd_ble_name', cats.ble_name,          fresh.ble_name);

    // Mode badge
    var mode=d.mode||'IDLE';
    var mb=$('modeLabel');
    mb.textContent=mode;
    mb.className='badge '+(mode==='INHALE'?'b-inhale':mode==='EXHALE'?'b-exhale':mode==='ERROR'?'b-error':'b-idle');

    // UART / ESP32-S3 status
    $('uartDot').className='dot '+(uart.connected?'dot-on':'dot-off');
    var lastPush=uart.last_push?new Date(uart.last_push*1000).toLocaleTimeString():'never';
    $('uartStatus').textContent='ESP32 UART: '+(uart.connected?'Connected':'Disconnected')+
      ' | Pushes: '+(uart.push_count||0)+
      ' | Last: '+lastPush+
      (uart.last_error?' | Err: '+uart.last_error:'');

    // ESP32 status card
    if($('esp32_link')){
      $('esp32_link').textContent=uart.connected?'Connected':'Disconnected';
      $('esp32_link').style.color=uart.connected?'#4c8':'#e07';
      $('esp32_pushes').textContent=uart.push_count||0;
      $('esp32_last_push').textContent=lastPush;
      $('esp32_error').textContent=uart.last_error||'None';
      $('esp32_sample_size').textContent=d.config?
        (d.config.uart_sample_size||50)+' (configured max)':'--';
    }

    // Log
    if(d.log&&d.log.length){
      $('logBox').textContent=d.log.join(String.fromCharCode(10));
      $('logBox').scrollTop=$('logBox').scrollHeight;
    }
    if(d.uptime) $('uptime').textContent='Uptime: '+d.uptime;
    if(_detailVisible) loadDetail();
  }catch(e){
    $('logBox').textContent='Status error: '+e;
  }
  loadPhaseBStatus();
}

function toggleDetail(){
  _detailVisible=$('showDetail').checked;
  $('detailSection').style.display=_detailVisible?'block':'none';
  if(_detailVisible) loadDetail();
}

var _CAT_LABELS = {
  ble_mac:'BLE MACs', ble_uuid:'BLE UUIDs', ble_name:'BLE Names',
  ble_manuf:'Manufacturer Data', wifi_probe_mac:'WiFi Probe MACs',
  wifi_ssid:'WiFi SSIDs', wifi_bssid:'WiFi BSSIDs',
  wifi_client_mac:'WiFi Client MACs'
};
var _CAT_ORDER = ['wifi_probe_mac','wifi_ssid','wifi_bssid','wifi_client_mac',
                  'ble_mac','ble_uuid','ble_name','ble_manuf'];

async function loadDetail(){
  try{
    var r=await fetch('/api/pool/detail');
    var d=await r.json();
    var html='';
    for(var i=0;i<_CAT_ORDER.length;i++){
      var cat=_CAT_ORDER[i];
      var vals=d[cat]||[];
      var label=_CAT_LABELS[cat];
      html+='<div class="detail-card"><div class="detail-cat">';
      html+='<span>'+label+'</span>';
      html+='<button class="btn btn-o btn-sm" data-cat="'+cat+'" data-lbl="'+label+'" onclick="showSnapBtn(this)">Full Pool</button>';
      html+='</div>';
      if(vals.length===0){
        html+='<div class="detail-empty">empty</div>';
      } else {
        for(var j=0;j<vals.length;j++){
          html+='<div class="detail-val">'+vals[j]+'</div>';
        }
      }
      html+='</div>';
    }
    $('detailGrid').innerHTML=html;
  }catch(e){
    $('detailGrid').innerHTML='<div style="color:#f87171">Error: '+e+'</div>';
  }
}

function showSnapBtn(btn){
  showSnap(btn.getAttribute('data-cat'), btn.getAttribute('data-lbl'));
}

async function showSnap(cat, label){
  $('snapTitle').textContent='Full Pool — '+label;
  $('snapList').textContent='Loading...';
  $('snapModal').style.display='block';
  try{
    var r=await fetch('/api/pool/full?cat='+cat);
    var d=await r.json();
    var vals=d.values||[];
    if(vals.length===0){
      $('snapList').textContent='(empty)';
    } else {
      $('snapList').textContent=vals.join(String.fromCharCode(10));
    }
    var now=new Date();
    $('snapTime').textContent=now.toLocaleTimeString()+' ('+vals.length+' items)';
  }catch(e){
    $('snapList').textContent='Error: '+e;
  }
}

function closeSnap(e){
  if(e.target===document.getElementById('snapModal'))
    document.getElementById('snapModal').style.display='none';
}

async function saveConfig(){
  var pw=$('mgmt_ap_password').value;
  var data={
    inhale_duration:      parseInt($('inhale_duration').value)||60,
    inhale_frequency:     parseInt($('inhale_frequency').value)||300,
    collect_ble_mac:      $('collect_ble_mac').checked,
    collect_ble_uuid:     $('collect_ble_uuid').checked,
    collect_ble_name:     $('collect_ble_name').checked,
    collect_ble_manuf:    $('collect_ble_manuf').checked,
    collect_wifi_probe:   $('collect_wifi_probe').checked,
    collect_wifi_beacon:  $('collect_wifi_beacon').checked,
    collect_wifi_assoc:   $('collect_wifi_assoc').checked,
    collect_wifi_deauth:  $('collect_wifi_deauth').checked,
    wifi_interface:       $('wifi_interface').value,
    wifi_channel:         parseInt($('wifi_channel').value)||6,
    max_pool_size:        parseInt($('max_pool_size').value)||2000,
    pool_retention_hours: parseInt($('pool_retention_hours').value)||2,
    exhale_interval:      parseInt($('exhale_interval').value)||30,
    uart_port:            $('uart_port').value,
    uart_baud:            parseInt($('uart_baud').value)||115200,
    uart_sync_interval:   parseInt($('uart_sync_interval').value)||15,
    uart_sample_size:     parseInt($('uart_sample_size').value)||50,
    ssid_inject_enabled:  $('ssid_inject_enabled').checked,
    ssid_inject_interface:$('ssid_inject_interface').value,
    ssid_inject_rate:     parseInt($('ssid_inject_rate').value)||20,
    ble_mac_spoof_enabled:$('ble_mac_spoof_enabled').checked,
    ble_mac_spoof_interface:$('ble_mac_spoof_interface').value,
    ble_mac_spoof_interval:parseInt($('ble_mac_spoof_interval').value)||8,
    mgmt_ap_enabled:      $('mgmt_ap_enabled').checked,
    mgmt_ap_interface:    $('mgmt_ap_interface').value,
    mgmt_ap_ssid:         $('mgmt_ap_ssid').value,
    mgmt_ap_channel:      parseInt($('mgmt_ap_channel').value)||1,
  };
  if(pw) data.mgmt_ap_password=pw;
  var r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  var result=await r.json();
  toast(result.ok?'Config saved!':'Error: '+(result.error||'unknown'),result.ok);
  if(pw) $('mgmt_ap_password').value='';
}

async function forceInhale(){
  toast('Queuing inhale cycle...');
  await fetch('/api/action/inhale',{method:'POST'});
  setTimeout(loadStatus,2000);
}

async function forceUartPush(){
  var r=await fetch('/api/action/uart_push',{method:'POST'});
  var d=await r.json();
  toast(d.ok?'Pushed '+d.count+' IDs to ESP32':'Push failed',d.ok);
}

async function restartAP(){
  toast('Restarting management AP...');
  await fetch('/api/action/restart_ap',{method:'POST'});
  setTimeout(loadStatus,3000);
}

async function resetConfig(){
  if(!confirm('Reset all settings to defaults?')) return;
  await fetch('/api/reset',{method:'POST'});
  toast('Reset complete.');
  setTimeout(loadStatus,500);
}

function clearLog(){$('logBox').textContent='';}

loadStatus();
setInterval(loadStatus,8000);
</script>
</body>
</html>
"""


def create_app(config, pool, logger, uart_sync, action_queue,
               ble_spoofer=None, ssid_injector=None):
    app = Flask(__name__)
    _start = time.time()

    @app.route("/favicon.ico")
    def favicon():
        # Minimal green flask/tube icon as 1-colour ICO
        from flask import Response
        import base64
        # 16x16 ICO with a single green pixel — suppresses 404 cleanly
        ico = base64.b64decode(
            "AAABAAEAEBAAAAEAGAAoAAAAFgAAACgAAAAQAAAAIAAAAAEAGAAAAAAA"
            "ACAAAAAAAAAAAAAAAAAAAAAA4aDAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        return Response(ico, mimetype="image/x-icon",
                        headers={"Cache-Control": "max-age=86400"})

    @app.route("/")
    def index():
        resp = make_response(_HTML)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma']  = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp

    @app.route("/api/status")
    def api_status():
        up = int(time.time() - _start)
        h, r = divmod(up, 3600)
        m, s = divmod(r, 60)
        mode = "IDLE"
        for item in action_queue:
            if item in ("IDLE","INHALE","EXHALE","ERROR"):
                mode = item
                break
        return jsonify({
            "mode":   mode,
            "config": config.as_dict(),
            "pool":   pool.stats(),
            "uart":   uart_sync.status(),
            "log":    logger.recent(60),
            "uptime": f"{h:02d}:{m:02d}:{s:02d}",
        })

    @app.route("/api/pool/detail")
    def api_pool_detail():
        return jsonify(pool.get_sample_by_category(n=5))

    @app.route("/api/pool/full")
    def api_pool_full():
        """Return all values for a single category — one-shot snapshot."""
        cat = request.args.get("cat", "")
        data = pool.get_sample_by_category(n=99999)
        vals = data.get(cat, [])
        vals.sort()
        return jsonify({"cat": cat, "count": len(vals), "values": vals})

    @app.route("/api/phase_b_status")
    def api_phase_b_status():
        """Current MAC/SSID being broadcast — reads from engine state and OS."""
        result = {
            "current_mac":    None,
            "mac_cycle_count": 0,
            "os_mac":         None,
            "last_ssid":      None,
            "last_bssid":     None,
            "ssid_beacon_count": 0,
        }
        if ble_spoofer:
            st = ble_spoofer.status()
            result["current_mac"]     = st.get("current_mac")
            result["mac_cycle_count"] = st.get("cycle_count", 0)
            # The nRF52840 (Zephyr hci_usb) does not expose the LE random address
            # via any standard read-back HCI command — the address is write-only
            # via OCF 0x0005. current_mac is only set when both _hci_set_random_addr
            # AND _start_advertising return True, so it already represents a confirmed
            # successful HCI transaction. Report that fact directly.
            result["os_mac"] = "ok" if result["current_mac"] else "fail"
        if ssid_injector:
            st = ssid_injector.status()
            result["last_ssid"]         = st.get("last_ssid")
            result["last_bssid"]        = st.get("last_bssid")
            result["ssid_beacon_count"] = st.get("beacon_count", 0)
        return jsonify(result)

    @app.route("/api/config", methods=["POST"])
    def api_config():
        try:
            data = request.get_json(force=True)
            prev_ap   = config.get("mgmt_ap_enabled", False)
            prev_ssid = config.get("ssid_inject_enabled", False)
            prev_ble  = config.get("ble_mac_spoof_enabled", False)
            config.update(data)
            config.save()
            new_ap   = config.get("mgmt_ap_enabled", False)
            new_ssid = config.get("ssid_inject_enabled", False)
            new_ble  = config.get("ble_mac_spoof_enabled", False)
            if prev_ap and not new_ap:
                action_queue.append("stop_ap")
            elif not prev_ap and new_ap:
                action_queue.append("restart_ap")
            if prev_ssid and not new_ssid:
                action_queue.append("stop_ssid")
            elif not prev_ssid and new_ssid:
                action_queue.append("start_ssid")
            if prev_ble and not new_ble:
                action_queue.append("stop_ble_spoof")
            elif not prev_ble and new_ble:
                action_queue.append("start_ble_spoof")
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    @app.route("/api/action/inhale", methods=["POST"])
    def api_inhale():
        action_queue.append("inhale")
        return jsonify({"ok": True})

    @app.route("/api/action/uart_push", methods=["POST"])
    def api_uart_push():
        ok    = uart_sync.push_sample()
        count = config.get("uart_sample_size", 50) if ok else 0
        return jsonify({"ok": ok, "count": count})

    @app.route("/api/action/restart_ap", methods=["POST"])
    def api_restart_ap():
        action_queue.append("restart_ap")
        return jsonify({"ok": True})

    @app.route("/api/reset", methods=["POST"])
    def api_reset():
        config.reset()
        return jsonify({"ok": True})

    return app
