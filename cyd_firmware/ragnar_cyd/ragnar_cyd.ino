/*
 * ragnar_cyd.ino — Ragnar CYD hybrid node (Piglet Core, 2.4 GHz)
 *
 * Target: ESP32-2432S028R "Cheap Yellow Display" (CYD)
 *   ESP32-WROOM-32 • 2.8" ILI9341 240x320 • XPT2046 resistive touch
 *
 * ROLE — a hybrid companion to a Ragnar Pi. It is NOT Ragnar: Ragnar (Flask on
 * Linux) cannot run on a WROOM-32. The node instead
 *   (1) shows a native touch dashboard of Ragnar's live status, and
 *   (2) lets the operator trigger a small allowlist of Ragnar actions, and
 *   (3) scans 2.4 GHz (WiFi promiscuous + BLE adverts) with its OWN radio and
 *       reports the counts back to Ragnar.
 *
 * The single 2.4 GHz radio cannot be joined to WiFi AND sniff other channels at
 * the same time, so the node TIME-SHARES in a duty cycle:
 *
 *   CONNECT+SYNC  -> (GET /api/cyd/status, POST /api/cyd/ingest, flush actions)
 *        |
 *   DISCONNECT -> WiFi promiscuous sweep ch 1..13
 *        |
 *   DISCONNECT -> BLE advertisement scan        (loops)
 *
 * The screen always renders the last-synced values, so status/findings are
 * near-real-time, not continuous. This is the price of a WROOM-32 vs an S3/C5.
 *
 * Build (arduino-cli):
 *   --fqbn "esp32:esp32:esp32:PartitionScheme=huge_app,FlashSize=4M"
 * Required library (already used elsewhere in Ragnar):
 *   "GFX Library for Arduino" by moononournation
 *
 * See cyd_firmware/README.md for flashing and Ragnar-side setup.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <SPI.h>
#include <esp_wifi.h>
#include <Arduino_GFX_Library.h>

#include "config.h"

// Defined before the first include-terminated section so Arduino's auto-generated
// prototypes (inserted after the includes) can reference ActionBtn*.
struct ActionBtn { const char *label; const char *action; };

#if CYD_ENABLE_BLE
#include <BLEDevice.h>
#include <BLEScan.h>
#endif

// ── Runtime configuration (NVS-backed; provisioned via the setup portal) ──────
struct RuntimeConfig {
  String ssid, pass, url, token, name;
};
static RuntimeConfig g_cfg;
static Preferences g_prefs;

// Load config from NVS, falling back to the (optional) compile-time seeds.
// Device settings (Settings screen), persisted in NVS.
static bool    g_bleEnabled   = true;    // BLE scanning on/off
static uint8_t g_backlightPct = 100;     // backlight brightness 0..100

static void loadConfig() {
  g_prefs.begin("ragnarcyd", true);
  g_cfg.ssid  = g_prefs.getString("ssid",  CYD_WIFI_SSID);
  g_cfg.pass  = g_prefs.getString("pass",  CYD_WIFI_PASS);
  g_cfg.url   = g_prefs.getString("url",   CYD_RAGNAR_URL);
  g_cfg.token = g_prefs.getString("token", CYD_DEVICE_TOKEN);
  g_cfg.name  = g_prefs.getString("name",  CYD_NODE_NAME);
  g_bleEnabled   = g_prefs.getBool("ble", true);
  g_backlightPct = g_prefs.getUChar("bl", 100);
  g_prefs.end();
  if (g_cfg.name.length() == 0) g_cfg.name = "cyd-node";
  if (g_backlightPct < 10) g_backlightPct = 10;
}

static void saveSettings() {
  g_prefs.begin("ragnarcyd", false);
  g_prefs.putBool("ble", g_bleEnabled);
  g_prefs.putUChar("bl", g_backlightPct);
  g_prefs.end();
}

// Apply the backlight brightness (LEDC PWM; keep a floor so it never goes black).
static void applyBacklight() {
  analogWrite(TFT_BL, map(g_backlightPct, 0, 100, 26, 255));
}

static void saveConfig(const RuntimeConfig &c) {
  g_prefs.begin("ragnarcyd", false);
  g_prefs.putString("ssid",  c.ssid);
  g_prefs.putString("pass",  c.pass);
  g_prefs.putString("url",   c.url);
  g_prefs.putString("token", c.token);
  g_prefs.putString("name",  c.name.length() ? c.name : String("cyd-node"));
  g_prefs.end();
}

// Enough to attempt operation: a WiFi SSID, a Ragnar URL and a device token.
static bool haveConfig() {
  return g_cfg.ssid.length() && g_cfg.url.length() && g_cfg.token.length();
}

// Arduino_GFX 1.6.7 exposes colors as RGB565_*; alias the two bare names we use.
#define WHITE RGB565_WHITE
#define BLACK RGB565_BLACK

// ── Display ───────────────────────────────────────────────────────────────────
static Arduino_DataBus *bus = new Arduino_ESP32SPI(
    TFT_DC, TFT_CS, TFT_SCLK, TFT_MOSI, TFT_MISO, VSPI);
static Arduino_GFX *gfx = new Arduino_ILI9341(bus, TFT_RST, 0 /*rotation*/, false /*IPS*/);

static const int16_t SCR_W = 240;
static const int16_t SCR_H = 320;

// ── Touch (XPT2046 on its own SPI bus) ────────────────────────────────────────
static SPIClass touchSPI(HSPI);

// ── UI state ──────────────────────────────────────────────────────────────────
// App-launcher model: a HOME grid of tiles that drill into full screens.
enum Screen { SCR_HOME = 0, SCR_DASH, SCR_DEFENSE, SCR_ALERTS, SCR_SCAN, SCR_SIGINT,
              SCR_WFALL, SCR_NETWORK, SCR_SETTINGS, SCR_CTRL, SCR_TOUCHTEST };
static Screen g_screen     = SCR_HOME;
static bool   g_needRedraw = true;

// ── Live model: last status synced from Ragnar ────────────────────────────────
struct RagnarStatus {
  bool     ok        = false;
  int      meshNodes = 0;
  int      nets24    = 0;
  int      nets5     = 0;
  int      threat    = 0;      // 0..100 threat score
  char     btState[16]      = "?";
  char     unitName[24]     = "ragnar";
  uint32_t uptimeSec        = 0;
  uint32_t lastSyncMs       = 0;
  // Expanded status fields (DASH / NETWORK / ALERTS):
  char     iface[12]        = "";
  char     ip[20]           = "";
  char     wardrive[16]     = "off";
  char     worst[10]        = "none";
  int      alerts           = 0;
  bool     wids             = false;
  char     alert1[30]       = "";
  char     alert2[30]       = "";
  char     alert3[30]       = "";
};
static RagnarStatus g_rs;

// ── Local sensor counters (this node's own radio) ─────────────────────────────
struct SensorCounts {
  volatile uint32_t beacons  = 0;
  volatile uint32_t probes   = 0;
  volatile uint32_t deauths  = 0;
  volatile uint32_t frames   = 0;
  uint32_t          bssids   = 0;   // unique BSSIDs this window
  uint32_t          bleAdv   = 0;   // BLE advertisements this window
};
static SensorCounts g_sc;

// Per-window AP sightings (RAM-bounded): BSSID + SSID + channel + strongest RSSI.
// Reported to Ragnar so its WiFi-Defense side can flag new/rogue APs.
#define MAX_AP 48
struct ApInfo {
  uint8_t bssid[6];
  char    ssid[33];
  uint8_t ch;
  int8_t  rssi;
};
static ApInfo   g_aps[MAX_AP];
static uint32_t g_apCount = 0;

// ── RF waterfall (downsampled spectrum streamed from Ragnar's SDR) ─────────────
// The CYD has no SDR; when the Waterfall screen is open it asks Ragnar to sweep
// a band and stream one quantised row per frame, which we scroll here.
#define WF_BINS 120
#define WF_ROWS 150
static uint8_t  g_wfImg[WF_ROWS][WF_BINS];   // ring of rows (0=strong..)
static int      g_wfHead = 0;                // next write row
static bool     g_wfHave = false;            // got at least one row
static uint32_t g_wfSeq  = 0;                // last applied row seq
static int      g_wfLo = 0, g_wfHi = 0;      // band edges, MHz
static char     g_wfErr[24] = "";            // e.g. "no SDR"
// Bands the CYD cycles: sub-GHz ISM first, then a few RF bands.
static const char *WF_BANDS[] = {"433", "868", "915", "315", "fm", "air", "2.4"};
static const int   WF_NBANDS  = 7;
static int         g_wfBandIdx = 0;
static bool        g_wfActive  = false;      // screen open -> streaming requested
static void applyWfRow(const String &body);  // defined in the UI section

// ── Pending action queue (taps flushed on next sync window) ───────────────────
#define MAX_ACTIONS 6
static String g_actionQ[MAX_ACTIONS];
static uint8_t g_actionHead = 0, g_actionTail = 0;

static bool actionEnqueue(const String &a) {
  uint8_t next = (uint8_t)((g_actionTail + 1) % MAX_ACTIONS);
  if (next == g_actionHead) return false;   // full
  g_actionQ[g_actionTail] = a;
  g_actionTail = next;
  return true;
}
static bool actionDequeue(String &out) {
  if (g_actionHead == g_actionTail) return false;
  out = g_actionQ[g_actionHead];
  g_actionHead = (uint8_t)((g_actionHead + 1) % MAX_ACTIONS);
  return true;
}

// ── Status line shown at the bottom of every page ─────────────────────────────
static char g_statusLine[40] = "booting";
static uint16_t g_statusColor = WHITE;
static void serviceUI();            // defined after render()/handleTouch()
static void setStatus(const char *s, uint16_t c) {
  // Only repaint when the text or colour actually changed — a periodic status
  // set with the same value must not force a redraw (that was part of the
  // every-few-seconds twitch).
  if (g_statusColor == c && strncmp(g_statusLine, s, sizeof(g_statusLine) - 1) == 0) return;
  strncpy(g_statusLine, s, sizeof(g_statusLine) - 1);
  g_statusLine[sizeof(g_statusLine) - 1] = 0;
  g_statusColor = c;
  g_needRedraw = true;
}

// ════════════════════════════════════════════════════════════════════════════
//  XPT2046 touch — minimal SPI reader (no external lib)
// ════════════════════════════════════════════════════════════════════════════
static uint16_t xptRead(uint8_t cmd) {
  touchSPI.beginTransaction(SPISettings(2000000, MSBFIRST, SPI_MODE0));
  digitalWrite(TOUCH_CS, LOW);
  touchSPI.transfer(cmd);
  uint16_t hi = touchSPI.transfer(0x00);
  uint16_t lo = touchSPI.transfer(0x00);
  digitalWrite(TOUCH_CS, HIGH);
  touchSPI.endTransaction();
  return ((hi << 8) | lo) >> 3;   // 12-bit result
}

// Last raw ADC sample (exposed for the touch-test screen).
static uint16_t g_lastRawX = 0, g_lastRawY = 0;

// Returns true and fills px/py (screen coords) when the panel is pressed.
static bool touchRead(int16_t &px, int16_t &py) {
  if (digitalRead(TOUCH_IRQ) == HIGH) return false;   // IRQ idles HIGH
  // Average a few samples to debounce the resistive panel.
  uint32_t sx = 0, sy = 0; int n = 0;
  for (int i = 0; i < 4; i++) {
    uint16_t rx = xptRead(0xD0);   // X
    uint16_t ry = xptRead(0x90);   // Y
    if (rx < 100 || ry < 100) continue;
    sx += rx; sy += ry; n++;
  }
  if (n == 0) return false;
  uint16_t rawx = sx / n, rawy = sy / n;
  g_lastRawX = rawx; g_lastRawY = rawy;
#if TOUCH_SWAP_XY
  { uint16_t t = rawx; rawx = rawy; rawy = t; }
#endif
  // Map raw ADC -> pixels (portrait), honouring the orientation flags so touch
  // lines up with the display. Clamp to screen.
#if TOUCH_INVERT_X
  long mx = map(rawx, TOUCH_RAW_MINX, TOUCH_RAW_MAXX, SCR_W - 1, 0);
#else
  long mx = map(rawx, TOUCH_RAW_MINX, TOUCH_RAW_MAXX, 0, SCR_W - 1);
#endif
#if TOUCH_INVERT_Y
  long my = map(rawy, TOUCH_RAW_MINY, TOUCH_RAW_MAXY, SCR_H - 1, 0);
#else
  long my = map(rawy, TOUCH_RAW_MINY, TOUCH_RAW_MAXY, 0, SCR_H - 1);
#endif
  px = (int16_t)constrain(mx, 0, SCR_W - 1);
  py = (int16_t)constrain(my, 0, SCR_H - 1);
  return true;
}

// ════════════════════════════════════════════════════════════════════════════
//  WiFi promiscuous sniffer
// ════════════════════════════════════════════════════════════════════════════
// Record a beacon's AP (BSSID/SSID/channel/RSSI). Called from the sniffer
// callback, so kept short: a bounded linear scan + a <=32-byte SSID copy.
static void apSeen(const wifi_promiscuous_pkt_t *pkt) {
  const uint8_t *p = pkt->payload;
  const uint8_t *bssid = &p[16];                 // addr3
  int8_t rssi = pkt->rx_ctrl.rssi;
  uint8_t ch = pkt->rx_ctrl.channel;
  for (uint32_t i = 0; i < g_apCount; i++) {
    if (memcmp(g_aps[i].bssid, bssid, 6) == 0) {
      if (rssi > g_aps[i].rssi) g_aps[i].rssi = rssi;   // keep the strongest
      return;
    }
  }
  if (g_apCount >= MAX_AP) return;
  ApInfo &a = g_aps[g_apCount];
  memcpy(a.bssid, bssid, 6);
  a.ch = ch;
  a.rssi = rssi;
  a.ssid[0] = 0;
  // SSID = tag 0 of the tagged params (beacon: 24-byte hdr + 12 fixed = off 36).
  int total = pkt->rx_ctrl.sig_len;
  if (total >= 38 && p[36] == 0) {
    int len = p[37];
    if (len > 32) len = 32;
    if (38 + len <= total) {
      int j = 0;
      for (int k = 0; k < len; k++) {
        char c = (char)p[38 + k];
        // Sanitize for JSON: printable ASCII only, no quote/backslash.
        a.ssid[j++] = (c >= 0x20 && c < 0x7F && c != '"' && c != '\\') ? c : '.';
      }
      a.ssid[j] = 0;
    }
  }
  g_apCount++;
}

static void IRAM_ATTR snifferCb(void *buf, wifi_promiscuous_pkt_type_t type) {
  if (type != WIFI_PKT_MGMT) return;
  const wifi_promiscuous_pkt_t *pkt = (wifi_promiscuous_pkt_t *)buf;
  const uint8_t *p = pkt->payload;
  g_sc.frames++;
  uint8_t subtype = (p[0] & 0xF0) >> 4;   // frame-control subtype
  switch (subtype) {
    case 0x08: g_sc.beacons++; apSeen(pkt); break;        // beacon (BSSID @ addr3)
    case 0x04: g_sc.probes++;  break;                     // probe request
    case 0x0C: g_sc.deauths++; break;                     // deauth
    case 0x0A: g_sc.deauths++; break;                     // disassoc (count as deauth)
    default: break;
  }
}

static void sniffReset() {
  g_sc.beacons = g_sc.probes = g_sc.deauths = g_sc.frames = 0;
  g_apCount = 0;
}

static void sniffWindow(uint32_t durationMs) {
  sniffReset();
  WiFi.disconnect(true, false);
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_promiscuous_rx_cb(&snifferCb);
  const uint8_t channels[] = {1, 6, 11, 2, 7, 12, 3, 8, 13, 4, 9, 5, 10};
  const int nch = sizeof(channels);
  uint32_t start = millis();
  uint32_t dwell = durationMs / (nch + 1);           // per-channel dwell
  if (dwell > 120) dwell = 120;
  int idx = 0;
  bool leave = false;
  while (millis() - start < durationMs && !leave) {
    esp_wifi_set_channel(channels[idx % nch], WIFI_SECOND_CHAN_NONE);
    idx++;
    // Cooperative dwell: keep touch + display alive while the sniffer callback
    // accumulates in the background (it's an async RX cb, not this loop). This
    // is what makes touch responsive during the 6 s sweep.
    uint32_t d0 = millis();
    while (millis() - d0 < dwell) {
      serviceUI(); delay(8);
#if CYD_TRANSPORT_SERIAL
      if (g_wfActive) { leave = true; break; }   // waterfall opened: end sweep now
#endif
    }
  }
  esp_wifi_set_promiscuous(false);
  g_sc.bssids = g_apCount;
}

// ════════════════════════════════════════════════════════════════════════════
//  BLE advertisement scan
// ════════════════════════════════════════════════════════════════════════════
#if CYD_ENABLE_BLE
static bool g_bleReady = false;
static volatile bool g_bleBusy = false;
static void bleDone(BLEScanResults res) {   // completion callback (async)
  g_sc.bleAdv = res.getCount();
  g_bleBusy = false;
}
// Start a passive BLE advert scan ASYNCHRONOUSLY (returns immediately); bleDone
// records the count when it finishes. The caller services the UI meanwhile, so
// BLE no longer blocks touch for its whole window.
static void bleStart(uint32_t durationMs) {
  if (!g_bleReady || g_bleBusy || !g_bleEnabled) return;   // Settings can disable BLE
  BLEScan *scan = BLEDevice::getScan();
  scan->setActiveScan(false);
  scan->setInterval(100);
  scan->setWindow(99);
  scan->clearResults();
  uint32_t secs = durationMs / 1000; if (secs < 1) secs = 1;
  g_bleBusy = true;
  if (!scan->start(secs, bleDone, false)) g_bleBusy = false;
}
#else
static void bleStart(uint32_t) { g_sc.bleAdv = 0; }
static const bool g_bleBusy = false;
#endif

// Build the "aps":[...] fragment for an ingest payload (shared by both
// transports). Capped so the line stays small; SSIDs were sanitised on capture.
#define AP_REPORT_MAX 32
static String apsJson() {
  String s = "\"aps\":[";
  uint32_t n = g_apCount < AP_REPORT_MAX ? g_apCount : AP_REPORT_MAX;
  char mac[18];
  for (uint32_t i = 0; i < n; i++) {
    const ApInfo &a = g_aps[i];
    snprintf(mac, sizeof(mac), "%02x:%02x:%02x:%02x:%02x:%02x",
             a.bssid[0], a.bssid[1], a.bssid[2], a.bssid[3], a.bssid[4], a.bssid[5]);
    if (i) s += ",";
    s += "{\"bssid\":\""; s += mac;
    s += "\",\"ssid\":\""; s += a.ssid;
    s += "\",\"ch\":"; s += String(a.ch);
    s += ",\"rssi\":"; s += String(a.rssi);
    s += "}";
  }
  s += "]";
  return s;
}

// ════════════════════════════════════════════════════════════════════════════
//  Ragnar REST client
// ════════════════════════════════════════════════════════════════════════════
// Flat-JSON helpers (we control the /api/cyd/status shape, so keep it simple).
static long jsonInt(const String &body, const char *key) {
  String k = String("\"") + key + "\"";
  int i = body.indexOf(k);
  if (i < 0) return 0;
  i = body.indexOf(':', i);
  if (i < 0) return 0;
  return body.substring(i + 1).toInt();
}
static String jsonStr(const String &body, const char *key) {
  String k = String("\"") + key + "\"";
  int i = body.indexOf(k);
  if (i < 0) return "";
  i = body.indexOf(':', i);
  if (i < 0) return "";
  int q1 = body.indexOf('"', i);
  if (q1 < 0) return "";
  int q2 = body.indexOf('"', q1 + 1);
  if (q2 < 0) return "";
  return body.substring(q1 + 1, q2);
}

// Apply a status JSON body (shared by the HTTP and serial transports).
static void applyStatus(const String &body) {
  g_rs.meshNodes = jsonInt(body, "mesh_nodes");
  g_rs.nets24    = jsonInt(body, "nets_24");
  g_rs.nets5     = jsonInt(body, "nets_5");
  g_rs.threat    = jsonInt(body, "threat");
  g_rs.uptimeSec = jsonInt(body, "uptime");
  g_rs.alerts = jsonInt(body, "alerts");
  g_rs.wids   = jsonInt(body, "wids") != 0;
  // Copy a string field into a fixed buffer (only if present, so a partial frame
  // doesn't wipe existing values).
  #define CYD_CPYS(field, key) do { String _v = jsonStr(body, key); \
    if (_v.length()) { strncpy(g_rs.field, _v.c_str(), sizeof(g_rs.field) - 1); \
      g_rs.field[sizeof(g_rs.field)-1] = 0; } } while (0)
  CYD_CPYS(btState, "bluetooth");
  CYD_CPYS(unitName, "unit");
  CYD_CPYS(iface, "iface");
  CYD_CPYS(ip, "ip");
  CYD_CPYS(wardrive, "wardrive");
  CYD_CPYS(worst, "worst");
  CYD_CPYS(alert1, "alert1");
  CYD_CPYS(alert2, "alert2");
  CYD_CPYS(alert3, "alert3");
  #undef CYD_CPYS
  g_rs.ok = true;
  g_rs.lastSyncMs = millis();
  // Only repaint when a DISPLAYED value actually changed. Ragnar pushes status
  // ~every 2 s with mostly-identical data; repainting every push is what made the
  // screen twitch. Build a cheap signature (excluding time-derived fields) and
  // redraw only on change.
  String sig = String(g_rs.meshNodes) + '|' + g_rs.nets24 + '|' + g_rs.nets5 + '|'
    + g_rs.threat + '|' + g_rs.alerts + '|' + g_rs.btState + '|' + g_rs.unitName + '|'
    + g_rs.iface + '|' + g_rs.ip + '|' + g_rs.wardrive + '|' + g_rs.worst + '|'
    + g_rs.alert1 + '|' + g_rs.alert2 + '|' + g_rs.alert3;
  static String lastSig;
  if (sig != lastSig) { lastSig = sig; g_needRedraw = true; }
}

#if !CYD_TRANSPORT_SERIAL
static bool httpGetStatus() {
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2500);
  http.begin(g_cfg.url + "/api/cyd/status");
  http.addHeader("Authorization", String("Bearer ") + g_cfg.token);
  int code = http.GET();
  if (code != 200) { http.end(); return false; }
  String body = http.getString();
  http.end();
  applyStatus(body);
  return true;
}

static bool httpPostIngest() {
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2500);
  http.begin(g_cfg.url + "/api/cyd/ingest");
  http.addHeader("Authorization", String("Bearer ") + g_cfg.token);
  http.addHeader("Content-Type", "application/json");
  String payload = String("{")
    + "\"node\":\"" + g_cfg.name + "\","
    + "\"beacons\":" + String((uint32_t)g_sc.beacons) + ","
    + "\"probes\":"  + String((uint32_t)g_sc.probes)  + ","
    + "\"deauths\":" + String((uint32_t)g_sc.deauths) + ","
    + "\"frames\":"  + String((uint32_t)g_sc.frames)  + ","
    + "\"bssids\":"  + String(g_sc.bssids) + ","
    + "\"ble_adv\":" + String(g_sc.bleAdv) + ","
    + "\"rssi\":"    + String(WiFi.RSSI()) + ","
    + apsJson() + "}";
  int code = http.POST(payload);
  http.end();
  return code == 200 || code == 204;
}

static bool httpPostAction(const String &action) {
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(3000);
  http.begin(g_cfg.url + "/api/cyd/action");
  http.addHeader("Authorization", String("Bearer ") + g_cfg.token);
  http.addHeader("Content-Type", "application/json");
  String payload = String("{\"node\":\"") + g_cfg.name + "\",\"action\":\"" + action + "\"}";
  int code = http.POST(payload);
  http.end();
  return code == 200 || code == 202;
}

// Connect to WiFi within the timeout. Returns true on success.
static bool wifiConnect() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(g_cfg.ssid.c_str(), g_cfg.pass.c_str());
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < CYD_WIFI_CONNECT_TO) {
    delay(150);
  }
  return WiFi.status() == WL_CONNECTED;
}
#endif // !CYD_TRANSPORT_SERIAL

// ════════════════════════════════════════════════════════════════════════════
//  USB-serial transport — newline-delimited JSON to/from cyd_serial_bridge.py
// ════════════════════════════════════════════════════════════════════════════
#if CYD_TRANSPORT_SERIAL
// Pi -> node: {"t":"st","unit":..,"mesh_nodes":..,"nets_24":..,"nets_5":..,
//              "threat":..,"bluetooth":"idle","uptime":..}
// node -> Pi: {"t":"in", <sensor counts>}   and   {"t":"ac","action":".."}
static void handleSerialLine(const String &line) {
  if (line.indexOf("\"wf\"") >= 0) { applyWfRow(line); return; }   // waterfall frame
  if (line.indexOf("\"st\"") >= 0) applyStatus(line);             // status frame
}

// Ask Ragnar to (start/stop) streaming the current band's spectrum.
static void serialSendWfReq(bool on) {
  Serial.print("{\"t\":\"wr\",\"band\":\"");
  Serial.print(WF_BANDS[g_wfBandIdx]);
  Serial.print("\",\"on\":"); Serial.print(on ? "1" : "0");
  Serial.println("}");
}

// Drain any pending inbound bytes and apply complete lines (non-blocking).
static void serialDrain() {
  static String buf;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') { if (buf.length()) handleSerialLine(buf); buf = ""; }
    else if (c != '\r' && buf.length() < 512) buf += c;
  }
}

static void serialSendIngest() {
  Serial.print("{\"t\":\"in\",\"node\":\"");
  Serial.print(g_cfg.name);
  Serial.print("\",\"beacons\":");  Serial.print((uint32_t)g_sc.beacons);
  Serial.print(",\"probes\":");     Serial.print((uint32_t)g_sc.probes);
  Serial.print(",\"deauths\":");    Serial.print((uint32_t)g_sc.deauths);
  Serial.print(",\"frames\":");     Serial.print((uint32_t)g_sc.frames);
  Serial.print(",\"bssids\":");     Serial.print(g_sc.bssids);
  Serial.print(",\"ble_adv\":");    Serial.print(g_sc.bleAdv);
  Serial.print(",");                Serial.print(apsJson());
  Serial.println("}");
}

static void serialSendAction(const String &action) {
  Serial.print("{\"t\":\"ac\",\"node\":\"");
  Serial.print(g_cfg.name);
  Serial.print("\",\"action\":\"");
  Serial.print(action);
  Serial.println("\"}");
}
#endif // CYD_TRANSPORT_SERIAL

// ════════════════════════════════════════════════════════════════════════════
//  UI
// ════════════════════════════════════════════════════════════════════════════
// ── Ragnar palette ────────────────────────────────────────────────────────────
static uint16_t colBg()    { return gfx->color565(11, 14, 20); }
static uint16_t colHead()  { return gfx->color565(16, 22, 34); }
static uint16_t colBlue()  { return gfx->color565(40, 120, 200); }
static uint16_t colSky()   { return gfx->color565(90, 180, 255); }
static uint16_t colGray()  { return gfx->color565(140, 152, 165); }
static uint16_t colDim()   { return gfx->color565(90, 100, 112); }
static uint16_t colGreen() { return gfx->color565(70, 200, 120); }
static uint16_t colAmber() { return gfx->color565(230, 170, 50); }
static uint16_t colRed()   { return gfx->color565(224, 64, 64); }

static uint16_t threatColor(int t) {
  if (t >= 66) return colRed();
  if (t >= 33) return colAmber();
  return colGreen();
}

// ── Launcher: a dense, data-driven 2-column menu (half-height tiles) ──────────
// Add a feature by adding one row to g_menu[] (and a case in render()/drawScreen)
// — the grid lays itself out. Up to 10 items fit without scrolling.
static const int16_t HEAD_H   = 30;
static const int16_t TILE_W   = 105;
static const int16_t TILE_H   = 38;                 // half the old tile height
static const int16_t TILE_XL  = 10, TILE_XR = 125;
static const int16_t MENU_Y0  = 36;                 // first row top
static const int16_t MENU_PITCH = TILE_H + 8;       // row stride

struct MenuItem { const char *label; Screen scr; uint8_t r, g, b; };
static const MenuItem g_menu[] = {
  {"DASH",     SCR_DASH,      40, 120, 200},
  {"DEFEND",   SCR_DEFENSE,   70, 200, 120},
  {"ALERTS",   SCR_ALERTS,   224,  64,  64},
  {"SCAN",     SCR_SCAN,     150,  90, 210},
  {"SIGINT",   SCR_SIGINT,    60, 190, 190},
  {"WFALL",    SCR_WFALL,    230, 170,  50},
  {"NET",      SCR_NETWORK,   80, 160, 120},
  {"SETTINGS", SCR_SETTINGS, 140, 152, 165},
  {"CTRL",     SCR_CTRL,     120, 130, 200},
};
static const int N_MENU = sizeof(g_menu) / sizeof(g_menu[0]);
static void menuItemXY(int i, int16_t &x, int16_t &y) {
  x = (i & 1) ? TILE_XR : TILE_XL;
  y = MENU_Y0 + (i / 2) * MENU_PITCH;
}

static void drawStatusBar() {
  gfx->fillRect(0, SCR_H - 22, SCR_W, 22, colHead());
  gfx->setTextSize(1);
  gfx->setTextColor(g_statusColor);
  gfx->setCursor(6, SCR_H - 15);
  gfx->print(g_statusLine);
}

static void kv(int16_t y, const char *k, const String &v, uint16_t vc) {
  // Clear this field's row first so a same-screen refresh needs no full wipe
  // (that's what removes the flicker) yet leaves no stale pixels behind.
  gfx->fillRect(0, y - 1, SCR_W, 30, colBg());
  gfx->setTextSize(1);
  gfx->setTextColor(colGray());
  gfx->setCursor(12, y);
  gfx->print(k);
  gfx->setTextColor(vc);
  gfx->setTextSize(2);
  gfx->setCursor(12, y + 10);
  gfx->print(v);
}

// Brand header (home) or a titled back-bar (drill-in screens).
static void drawHeader(const char *title, bool home) {
  gfx->fillRect(0, 0, SCR_W, HEAD_H, colHead());
  if (home) {
    // Title = this unit's identity (mesh short-name, or 'Ragnar' when no mesh) —
    // no fixed 'RAGNAR' brand + name (which read 'RAGNAR Ragnar' off-mesh).
    String u = g_rs.unitName; if (!u.length()) u = "Ragnar";
    if (u.length() > 18) u = u.substring(0, 18);
    gfx->setTextColor(colSky()); gfx->setTextSize(2);
    gfx->setCursor(8, 8); gfx->print(u);
  } else {
    // Bigger, obvious back target: a rounded chip filling the header-left, with a
    // large arrow. The touch zone (see handleTouch) is even larger than the chip.
    gfx->fillRoundRect(2, 2, 58, HEAD_H - 4, 6, gfx->color565(30, 90, 160));
    gfx->drawRoundRect(2, 2, 58, HEAD_H - 4, 6, colSky());
    gfx->setTextColor(WHITE); gfx->setTextSize(3);
    gfx->setCursor(14, 5); gfx->print("<");
    gfx->setTextSize(2);
    gfx->setTextColor(WHITE);
    gfx->setCursor(70, 8); gfx->print(title);
  }
}

// Back target: the full header, plus a generous top-left zone that extends below
// the header edge (resistive panels are least sensitive at the very top edge, so
// a taller/wider hit box makes "back" easy to hit).
static const int16_t BACK_ZONE_W = 90;
static const int16_t BACK_ZONE_H = HEAD_H + 12;
static bool inBackZone(int16_t px, int16_t py) {
  return (py < HEAD_H) || (px < BACK_ZONE_W && py < BACK_ZONE_H);
}

// A half-height menu tile: left accent bar + label, with a compact live value
// on the right where one is useful. Label stays legible up to ~8 chars.
static void drawMenuTile(int16_t x, int16_t y, const char *label,
                         const String &val, uint16_t accent, uint16_t vcol) {
  gfx->fillRoundRect(x, y, TILE_W, TILE_H, 6, gfx->color565(22, 28, 40));
  gfx->drawRoundRect(x, y, TILE_W, TILE_H, 6, gfx->color565(45, 55, 70));
  gfx->fillRoundRect(x, y + 4, 4, TILE_H - 8, 2, accent);   // left accent bar
  gfx->setTextColor(WHITE); gfx->setTextSize(2);
  gfx->setCursor(x + 12, y + (TILE_H - 16) / 2); gfx->print(label);
  if (val.length()) {
    gfx->setTextColor(vcol); gfx->setTextSize(1);
    int16_t vx = x + TILE_W - (int16_t)val.length() * 6 - 6;
    gfx->setCursor(vx, y + (TILE_H - 8) / 2); gfx->print(val);
  }
}

// Compact per-tile live value (empty where none is useful). Takes an int (not
// Screen) so Arduino's auto-prototype doesn't reference the enum before it's
// declared.
static String menuValue(int s, uint16_t &vcol) {
  vcol = colGray();
  switch (s) {
    case SCR_DASH:    vcol = threatColor(g_rs.threat); return String(g_rs.threat);
    case SCR_DEFENSE: { bool a = g_sc.deauths > 0; vcol = a ? colRed() : colGreen();
                        return a ? String((uint32_t)g_sc.deauths) : String("ok"); }
    case SCR_ALERTS:  vcol = g_rs.alerts ? colRed() : colGreen(); return String(g_rs.alerts);
    case SCR_SCAN:    vcol = colSky(); return String(g_sc.bssids);
    case SCR_SIGINT:  vcol = colSky(); return String(g_apCount);
    case SCR_WFALL:   vcol = colAmber(); return String(WF_BANDS[g_wfBandIdx]);
    case SCR_NETWORK: vcol = colSky(); return String(g_rs.nets24) + "/" + String(g_rs.nets5);
    default:          return String("");
  }
}

static void drawHome() {
  drawHeader(nullptr, true);
  for (int i = 0; i < N_MENU; i++) {
    int16_t x, y; menuItemXY(i, x, y);
    uint16_t vcol; String val = menuValue(g_menu[i].scr, vcol);
    drawMenuTile(x, y, g_menu[i].label, val,
                 gfx->color565(g_menu[i].r, g_menu[i].g, g_menu[i].b), vcol);
  }
}

static void drawDash() {
  drawHeader("DASHBOARD", false);
  int16_t y = HEAD_H + 8;   // no UNIT row — the name is on HOME already
  kv(y, "THREAT", String(g_rs.threat) + " / 100", threatColor(g_rs.threat)); y += 38;
  kv(y, "ALERTS", String(g_rs.alerts) + "  " + g_rs.worst,
     g_rs.alerts ? colRed() : colGreen()); y += 38;
  kv(y, "NETWORKS", String(g_rs.nets24) + " / " + String(g_rs.nets5) + " (2.4/5G)", WHITE); y += 38;
  kv(y, "WARDRIVE", String(g_rs.wardrive), WHITE); y += 38;
  if (strlen(g_rs.iface))
    kv(y, "LINK", String(g_rs.iface) + " " + g_rs.ip, colSky());
  else
    kv(y, "BLUETOOTH", String(g_rs.btState), WHITE);
  y += 38;
  uint32_t since = g_rs.lastSyncMs ? (millis() - g_rs.lastSyncMs) / 1000 : 0;
  kv(y, "LAST SYNC", String(since) + "s ago", g_rs.ok ? colGreen() : colRed());
}

static void drawDefense() {
  drawHeader("DEFENSE", false);
  int16_t y = HEAD_H + 8;
  // Headline banner: attack (red) vs watching (green)
  bool attack = g_sc.deauths > 0;
  gfx->fillRoundRect(10, y, SCR_W - 20, 30, 6, attack ? colRed() : gfx->color565(20, 60, 40));
  gfx->setTextColor(WHITE); gfx->setTextSize(2);
  gfx->setCursor(20, y + 8);
  gfx->print(attack ? "DEAUTH SEEN" : "WATCHING 2.4G");
  y += 44;
  kv(y, "DEAUTH/DISASSOC", String((uint32_t)g_sc.deauths), attack ? colRed() : WHITE); y += 38;
  kv(y, "APs THIS SWEEP", String(g_sc.bssids), WHITE); y += 38;
  kv(y, "PROBE REQUESTS", String((uint32_t)g_sc.probes), WHITE); y += 38;
  kv(y, "BLE DEVICES", String(g_sc.bleAdv), WHITE); y += 38;
  gfx->setTextSize(1); gfx->setTextColor(colDim());
  gfx->setCursor(12, y + 6); gfx->print("reported to Ragnar WiFi Defense");
}

static void drawScan() {
  drawHeader("SCAN 2.4 GHz", false);
  int16_t y = HEAD_H + 8;
  kv(y, "BEACONS", String((uint32_t)g_sc.beacons), WHITE); y += 38;
  kv(y, "UNIQUE APs", String(g_sc.bssids), WHITE); y += 38;
  kv(y, "PROBE REQ", String((uint32_t)g_sc.probes), WHITE); y += 38;
  kv(y, "DEAUTH/DISASSOC", String((uint32_t)g_sc.deauths), g_sc.deauths > 0 ? colRed() : WHITE); y += 38;
  kv(y, "BLE ADVERTS", String(g_sc.bleAdv), WHITE); y += 38;
  kv(y, "FRAMES SEEN", String((uint32_t)g_sc.frames), colDim());
}

// ── Signal Intelligence: a radar/dome view of the 2.4 GHz APs we hear ─────────
static void drawSigInt() {
  drawHeader("SIGINT", false);
  // Clear the plot area (moving dots would smear without the full-screen wipe).
  gfx->fillRect(0, HEAD_H, SCR_W, SCR_H - HEAD_H - 22, colBg());
  int16_t cx = SCR_W / 2;
  int16_t cy = HEAD_H + 118;
  int16_t rmax = 100;
  for (int r = rmax; r > 0; r -= rmax / 3)
    gfx->drawCircle(cx, cy, r, gfx->color565(28, 38, 50));
  gfx->drawCircle(cx, cy, rmax, colDim());
  gfx->fillCircle(cx, cy, 3, colSky());                 // this node = centre
  for (uint32_t i = 0; i < g_apCount; i++) {
    const ApInfo &a = g_aps[i];
    float frac = (-30.0f - a.rssi) / 60.0f;             // -30dBm→centre, -90→edge
    if (frac < 0) frac = 0; if (frac > 1) frac = 1;
    int rr = (int)(frac * rmax);
    uint32_t h = a.bssid[5] | (a.bssid[4] << 8) | (a.bssid[3] << 16);
    float ang = (h % 360) * 0.017453f;
    int px = cx + (int)(rr * cosf(ang));
    int py = cy + (int)(rr * sinf(ang));
    gfx->fillCircle(px, py, 2, a.rssi > -55 ? colGreen() : (a.rssi > -75 ? colAmber() : colRed()));
  }
  gfx->setTextColor(colDim()); gfx->setTextSize(1);
  gfx->setCursor(8, SCR_H - 38);
  gfx->print(String(g_apCount) + " APs  centre=here  outer ring=weak");
}

// ── RF waterfall: palette + a streamed-row renderer ───────────────────────────
static uint16_t wfColor(uint8_t v) {
  uint8_t r, g, b;
  if (v < 64)       { r = 0;             g = v * 4;             b = 128 + v / 2; }
  else if (v < 128) { r = 0;             g = 255;               b = 255 - (v - 64) * 4; }
  else if (v < 192) { r = (v - 128) * 4; g = 255;               b = 0; }
  else              { r = 255;           g = 255 - (v - 192) * 4;b = 0; }
  return gfx->color565(r, g, b);
}

static void drawWaterfall() {
  drawHeader("WATERFALL", false);
  int16_t by = HEAD_H;
  gfx->fillRect(0, by, SCR_W, 20, gfx->color565(24, 30, 42));
  gfx->setTextColor(colAmber()); gfx->setTextSize(2);
  gfx->setCursor(8, by + 3); gfx->print(WF_BANDS[g_wfBandIdx]);
  gfx->setTextColor(colDim()); gfx->setTextSize(1);
  if (g_wfLo) { gfx->setCursor(58, by + 7);
                gfx->print(String(g_wfLo) + "-" + String(g_wfHi) + "MHz"); }
  gfx->setTextColor(colSky()); gfx->setCursor(184, by + 7); gfx->print("band>");
  int16_t yTop = by + 22;
  int16_t hArea = (SCR_H - 22) - yTop;
  if (g_wfErr[0]) {
    gfx->setTextColor(colRed()); gfx->setTextSize(2);
    gfx->setCursor(16, yTop + 40); gfx->print(g_wfErr);
    gfx->setTextColor(colDim()); gfx->setTextSize(1);
    gfx->setCursor(16, yTop + 70); gfx->print("attach a HackRF/RTL-SDR to Ragnar");
    return;
  }
  if (!g_wfHave) {
    gfx->setTextColor(colDim()); gfx->setTextSize(1);
    gfx->setCursor(16, yTop + 40); gfx->print("waiting for spectrum...");
    return;
  }
  int rows = hArea < WF_ROWS ? hArea : WF_ROWS;
  for (int r = 0; r < rows; r++) {
    int src = (g_wfHead - 1 - r + WF_ROWS * 2) % WF_ROWS;   // newest at the top
    int y = yTop + r;
    for (int c = 0; c < WF_BINS; c++)
      gfx->fillRect(c * 2, y, 2, 1, wfColor(g_wfImg[src][c]));
  }
}

// Apply one streamed waterfall frame (shared by both transports).
static void applyWfRow(const String &body) {
  String err = jsonStr(body, "err");
  if (err.length()) {
    strncpy(g_wfErr, err.c_str(), sizeof(g_wfErr) - 1);
    g_wfErr[sizeof(g_wfErr) - 1] = 0;
    g_needRedraw = true;
    return;
  }
  g_wfErr[0] = 0;
  g_wfLo = jsonInt(body, "lo");
  g_wfHi = jsonInt(body, "hi");
  g_wfSeq = jsonInt(body, "seq");
  int i = body.indexOf("\"bins\"");
  if (i < 0) return;
  i = body.indexOf('[', i);
  int end = (i >= 0) ? body.indexOf(']', i) : -1;
  if (i < 0 || end < 0) return;
  int col = 0, p = i + 1;
  while (p < end && col < WF_BINS) {
    while (p < end && (body[p] == ' ' || body[p] == ',')) p++;
    int v = 0; bool any = false;
    while (p < end && body[p] >= '0' && body[p] <= '9') { v = v * 10 + (body[p] - '0'); p++; any = true; }
    if (!any) break;
    g_wfImg[g_wfHead][col++] = (uint8_t)(v > 255 ? 255 : v);
  }
  while (col < WF_BINS) g_wfImg[g_wfHead][col++] = 0;
  g_wfHead = (g_wfHead + 1) % WF_ROWS;
  g_wfHave = true;
  g_needRedraw = true;
}

// CONTROLS screen actions.
static const ActionBtn g_ctrlActions[] = {
  {"WiFi Defense scan", "wifi_defense_scan"},
  {"BLE scan",          "ble_scan"},
  {"Watchtower clear",  "watchtower_clear"},
  {"Restart Ragnar",    "service_restart"},
};
static const int N_CTRL = sizeof(g_ctrlActions) / sizeof(g_ctrlActions[0]);

// NETWORK screen actions — a dense 2-column grid (fits far more than 3 big
// buttons; add a row here and it lays itself out).
static const ActionBtn g_netActions[] = {
  {"Wardrive on",  "wardrive_start"},
  {"Wardrive off", "wardrive_stop"},
  {"Airspace",     "network_scan"},
  {"WIDS scan",    "wifi_defense_scan"},
  {"BLE scan",     "ble_scan"},
  {"Clear alerts", "watchtower_clear"},
};
static const int N_NET = sizeof(g_netActions) / sizeof(g_netActions[0]);

static const int16_t BTN_BH = 40, BTN_GAP = 8;

// Compact 2-column action grid (half-height buttons, size-1 labels).
static const int16_t GBTN_W = 105, GBTN_H = 34, GBTN_GAP = 7;
static void gridBtnXY(int i, int16_t y0, int16_t &x, int16_t &y) {
  x = (i & 1) ? 125 : 10;
  y = y0 + (i / 2) * (GBTN_H + GBTN_GAP);
}
static void drawActionGrid(const ActionBtn *items, int n, int16_t y0) {
  for (int i = 0; i < n; i++) {
    int16_t x, y; gridBtnXY(i, y0, x, y);
    gfx->fillRoundRect(x, y, GBTN_W, GBTN_H, 6, colBlue());
    gfx->drawRoundRect(x, y, GBTN_W, GBTN_H, 6, colSky());
    gfx->setTextColor(WHITE); gfx->setTextSize(1);
    gfx->setCursor(x + 8, y + (GBTN_H - 8) / 2); gfx->print(items[i].label);
  }
}
static bool hitActionGrid(const ActionBtn *items, int n, int16_t y0,
                          int16_t px, int16_t py) {
  for (int i = 0; i < n; i++) {
    int16_t x, y; gridBtnXY(i, y0, x, y);
    if (inRect(px, py, x, y, GBTN_W, GBTN_H)) {
      if (actionEnqueue(items[i].action))
        setStatus((String("queued: ") + items[i].label).c_str(), colAmber());
      else
        setStatus("action queue full", colRed());
      return true;
    }
  }
  return false;
}

// Draw a vertical list of action buttons from y0; returns the y after the list.
static int16_t drawActionList(const ActionBtn *items, int n, int16_t y0) {
  int16_t y = y0;
  for (int i = 0; i < n; i++) {
    gfx->fillRoundRect(10, y, SCR_W - 20, BTN_BH, 8, colBlue());
    gfx->drawRoundRect(10, y, SCR_W - 20, BTN_BH, 8, colSky());
    gfx->setTextColor(WHITE); gfx->setTextSize(2);
    gfx->setCursor(22, y + 12);
    gfx->print(items[i].label);
    y += BTN_BH + BTN_GAP;
  }
  return y;
}

// Hit-test an action list at y0; enqueues the tapped action. Returns true if hit.
static bool hitActionList(const ActionBtn *items, int n, int16_t y0,
                          int16_t px, int16_t py) {
  int16_t y = y0;
  for (int i = 0; i < n; i++) {
    if (inRect(px, py, 10, y, SCR_W - 20, BTN_BH)) {
      if (actionEnqueue(items[i].action))
        setStatus((String("queued: ") + items[i].label).c_str(), colAmber());
      else
        setStatus("action queue full", colRed());
      return true;
    }
    y += BTN_BH + BTN_GAP;
  }
  return false;
}

static const int16_t CTRL_Y0 = HEAD_H + 10;
static void drawControls() {
  drawHeader("CONTROLS", false);
  drawActionList(g_ctrlActions, N_CTRL, CTRL_Y0);
}

// ── Network: compact status header + wardrive/scan action buttons ─────────────
static const int16_t NET_GRID_Y0 = HEAD_H + 44;
static void drawNetwork() {
  drawHeader("NETWORK", false);
  // Condensed 2-line status header, then a dense action grid below.
  int16_t y = HEAD_H + 6;
  gfx->fillRect(0, y, SCR_W, 36, colBg());
  gfx->setTextSize(1);
  String l1 = (strlen(g_rs.iface) ? (String(g_rs.iface) + " " + g_rs.ip) : String("link --"))
              + "  " + String(g_rs.nets24) + "/" + String(g_rs.nets5) + "G";
  gfx->setTextColor(colSky()); gfx->setCursor(12, y); gfx->print(l1);
  gfx->setTextColor(colGray()); gfx->setCursor(12, y + 16); gfx->print("wdrv ");
  gfx->setTextColor(WHITE); gfx->print(g_rs.wardrive);
  gfx->setTextColor(colGray()); gfx->print("   alrt ");
  gfx->setTextColor(g_rs.alerts ? colRed() : colGreen());
  gfx->print(String(g_rs.alerts) + " " + g_rs.worst);
  drawActionGrid(g_netActions, N_NET, NET_GRID_Y0);
}

// ── Alerts: newest Watchtower findings pushed from Ragnar ─────────────────────
static void drawAlerts() {
  drawHeader("ALERTS", false);
  int16_t y = HEAD_H + 10;
  gfx->fillRect(0, y, SCR_W, SCR_H - HEAD_H - 32, colBg());
  gfx->setTextSize(2);
  uint16_t hc = g_rs.alerts ? colRed() : colGreen();
  gfx->setTextColor(hc);
  gfx->setCursor(12, y); gfx->print(String(g_rs.alerts) + " active");
  gfx->setTextColor(colDim()); gfx->setTextSize(1);
  gfx->setCursor(150, y + 4); gfx->print("worst: "); gfx->print(g_rs.worst);
  y += 30;
  const char *titles[3] = { g_rs.alert1, g_rs.alert2, g_rs.alert3 };
  bool any = false;
  for (int i = 0; i < 3; i++) {
    if (!strlen(titles[i])) continue;
    any = true;
    gfx->fillRoundRect(10, y, SCR_W - 20, 40, 6, gfx->color565(30, 22, 26));
    gfx->drawRoundRect(10, y, SCR_W - 20, 40, 6, gfx->color565(90, 50, 55));
    gfx->fillRoundRect(10, y + 4, 4, 32, 2, colRed());
    gfx->setTextColor(WHITE); gfx->setTextSize(1);
    gfx->setCursor(22, y + 15); gfx->print(titles[i]);
    y += 48;
  }
  if (!any) {
    gfx->setTextColor(colDim()); gfx->setTextSize(1);
    gfx->setCursor(12, y + 6); gfx->print("no recent alerts");
  }
  gfx->setTextColor(colDim()); gfx->setTextSize(1);
  gfx->setCursor(12, SCR_H - 40); gfx->print("tap CTRL to clear the Watchtower pane");
}

// ── Settings: device-local, tappable rows + info. Persisted to NVS ────────────
static const char *FW_BUILD = "cyd 0.5 " __DATE__;
static const int16_t SET_Y0 = HEAD_H + 10, SET_ROWH = 32, SET_PITCH = 40;

static void drawSettingRow(int16_t y, const char *label, const String &val, uint16_t vcol) {
  gfx->fillRoundRect(10, y, SCR_W - 20, SET_ROWH, 6, gfx->color565(28, 34, 48));
  gfx->drawRoundRect(10, y, SCR_W - 20, SET_ROWH, 6, gfx->color565(50, 60, 78));
  gfx->setTextColor(WHITE); gfx->setTextSize(2);
  gfx->setCursor(20, y + 8); gfx->print(label);
  gfx->setTextColor(vcol); gfx->setTextSize(2);
  int16_t vx = SCR_W - 20 - (int16_t)val.length() * 12 - 8;
  gfx->setCursor(vx, y + 8); gfx->print(val);
}

static void drawSettings() {
  drawHeader("SETTINGS", false);
  drawSettingRow(SET_Y0, "BLE scan", g_bleEnabled ? "ON" : "OFF",
                 g_bleEnabled ? colGreen() : colGray());
  drawSettingRow(SET_Y0 + SET_PITCH, "Backlight", String(g_backlightPct) + "%", colSky());
  drawSettingRow(SET_Y0 + SET_PITCH * 2, "Touch test", "open", colAmber());
  int16_t y = SET_Y0 + SET_PITCH * 3 + 4;
  kv(y, "NODE", g_cfg.name, colSky());                         y += 32;
  kv(y, "FIRMWARE", String(FW_BUILD), WHITE);                  y += 32;
  kv(y, "FREE HEAP", String(ESP.getFreeHeap() / 1024) + " KB", colDim());
}

// ── Touch test / orientation validator ────────────────────────────────────────
// Hold the board antenna-UP. The banner must read at the TOP (antenna end) — that
// confirms display orientation. Then tap each labelled corner: the dot must land
// under your finger — that confirms touch mapping. If a corner is wrong, note
// which and the TOUCH_INVERT_X/Y / TOUCH_SWAP_XY flags in config.h get set.
static int16_t g_ttX = -1, g_ttY = -1;
static void drawTouchTest() {
  drawHeader("TOUCH TEST", false);
  int16_t top = HEAD_H, bot = SCR_H - 22;
  gfx->fillRect(0, top, SCR_W, bot - top, colBg());
  // TOP banner (antenna end) + corner labels
  gfx->setTextColor(colAmber()); gfx->setTextSize(1);
  gfx->setCursor(60, top + 4); gfx->print("^ TOP - antenna up ^");
  gfx->setTextColor(colDim());
  gfx->setCursor(6, top + 16);            gfx->print("TL");
  gfx->setCursor(SCR_W - 20, top + 16);   gfx->print("TR");
  gfx->setCursor(6, bot - 12);            gfx->print("BL");
  gfx->setCursor(SCR_W - 20, bot - 12);   gfx->print("BR");
  // centre crosshair
  gfx->drawFastHLine(SCR_W/2 - 10, (top+bot)/2, 20, gfx->color565(40,50,64));
  gfx->drawFastVLine(SCR_W/2, (top+bot)/2 - 10, 20, gfx->color565(40,50,64));
  // last tap marker + readout
  if (g_ttX >= 0) {
    gfx->drawCircle(g_ttX, g_ttY, 8, colSky());
    gfx->fillCircle(g_ttX, g_ttY, 3, colRed());
    gfx->setTextColor(WHITE); gfx->setTextSize(1);
    gfx->setCursor(6, (top+bot)/2 + 14);
    gfx->print("x="); gfx->print(g_ttX); gfx->print(" y="); gfx->print(g_ttY);
    gfx->setTextColor(colDim());
    gfx->setCursor(6, (top+bot)/2 + 26);
    gfx->print("raw "); gfx->print(g_lastRawX); gfx->print(","); gfx->print(g_lastRawY);
  } else {
    gfx->setTextColor(colGray()); gfx->setTextSize(1);
    gfx->setCursor(30, (top+bot)/2 + 20); gfx->print("tap the labelled corners");
  }
  gfx->setTextColor(colDim()); gfx->setTextSize(1);
  gfx->setCursor(6, bot + 2); gfx->print("tap < to exit");
}

static void render() {
  // Only wipe the whole panel when the SCREEN changes; a same-screen refresh
  // repaints its own field backgrounds (kv/tiles/etc), so a periodic data update
  // no longer black-flashes the display every few seconds (the "twitch").
  static Screen g_rendered = (Screen)255;
  if (g_screen != g_rendered) { gfx->fillScreen(colBg()); g_rendered = g_screen; }
  switch (g_screen) {
    case SCR_HOME:    drawHome();      break;
    case SCR_DASH:    drawDash();      break;
    case SCR_DEFENSE: drawDefense();   break;
    case SCR_ALERTS:  drawAlerts();    break;
    case SCR_SCAN:    drawScan();      break;
    case SCR_SIGINT:  drawSigInt();    break;
    case SCR_WFALL:   drawWaterfall(); break;
    case SCR_NETWORK: drawNetwork();   break;
    case SCR_SETTINGS:drawSettings();  break;
    case SCR_CTRL:    drawControls();  break;
    case SCR_TOUCHTEST: drawTouchTest(); break;
  }
  drawStatusBar();
  g_needRedraw = false;
}

static bool inRect(int16_t px, int16_t py, int16_t x, int16_t y, int16_t w, int16_t h) {
  return px >= x && px < x + w && py >= y && py < y + h;
}

// Reset the waterfall image (band change / (re)open).
static void wfReset() {
  g_wfHave = false; g_wfHead = 0; g_wfErr[0] = 0; g_wfLo = g_wfHi = 0;
}

// Touch: HOME picks a tile; a drill-in screen's header returns HOME; CONTROLS
// buttons enqueue an action; WATERFALL's band bar cycles the band.
static void handleTouch(int16_t px, int16_t py) {
  if (g_screen == SCR_HOME) {
    for (int i = 0; i < N_MENU; i++) {
      int16_t x, y; menuItemXY(i, x, y);
      if (!inRect(px, py, x, y, TILE_W, TILE_H)) continue;
      g_screen = g_menu[i].scr;
      if (g_screen == SCR_WFALL) {
        wfReset();
#if CYD_TRANSPORT_SERIAL
        g_wfActive = true;                        // stream over the cable
#else
        strncpy(g_wfErr, "USB-serial only", sizeof(g_wfErr) - 1);
#endif
      }
      g_needRedraw = true;
      return;
    }
    return;
  }
  // Back: enlarged hit zone everywhere except WFALL, whose band bar sits right
  // under the header (there, back stays header-only so band-cycling is usable).
  bool back = (g_screen == SCR_WFALL) ? (py < HEAD_H) : inBackZone(px, py);
  if (back) {
    if (g_screen == SCR_WFALL) g_wfActive = false;
    g_screen = SCR_HOME; g_needRedraw = true; return;
  }
  if (g_screen == SCR_SETTINGS) {
    if (inRect(px, py, 10, SET_Y0, SCR_W - 20, SET_ROWH)) {
      g_bleEnabled = !g_bleEnabled; saveSettings(); g_needRedraw = true; return;
    }
    if (inRect(px, py, 10, SET_Y0 + SET_PITCH, SCR_W - 20, SET_ROWH)) {
      g_backlightPct = g_backlightPct > 66 ? 66 : (g_backlightPct > 33 ? 33 : 100);
      applyBacklight(); saveSettings(); g_needRedraw = true; return;
    }
    if (inRect(px, py, 10, SET_Y0 + SET_PITCH * 2, SCR_W - 20, SET_ROWH)) {
      g_ttX = g_ttY = -1; g_screen = SCR_TOUCHTEST; g_needRedraw = true; return;
    }
    return;
  }
  if (g_screen == SCR_TOUCHTEST) {
    g_ttX = px; g_ttY = py; g_needRedraw = true;            // mark the tap
    // Diagnostic line for host-side calibration (ignored by the JSON bridge).
    Serial.print("TT raw="); Serial.print(g_lastRawX); Serial.print(",");
    Serial.print(g_lastRawY); Serial.print(" map="); Serial.print(px);
    Serial.print(","); Serial.println(py);
    return;
  }
  if (g_screen == SCR_WFALL) {
    // Tap the band bar (top strip) to cycle to the next band.
    if (py >= HEAD_H && py < HEAD_H + 20) {
      g_wfBandIdx = (g_wfBandIdx + 1) % WF_NBANDS;
      wfReset();
      g_needRedraw = true;
    }
    return;
  }
  if (g_screen == SCR_CTRL) {
    hitActionList(g_ctrlActions, N_CTRL, CTRL_Y0, px, py);
    return;
  }
  if (g_screen == SCR_NETWORK) {
    hitActionGrid(g_netActions, N_NET, NET_GRID_Y0, px, py);
    return;
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  Setup portal — SoftAP + captive form to provision WiFi / URL / token / name
//  (WiFi transport only; the serial build is cabled and needs no provisioning)
// ════════════════════════════════════════════════════════════════════════════
#if !CYD_TRANSPORT_SERIAL
static WebServer g_portalServer(80);
static DNSServer g_portalDNS;

static String htmlAttr(const String &s) {
  String o; o.reserve(s.length() + 8);
  for (size_t i = 0; i < s.length(); i++) {
    char c = s[i];
    if (c == '&') o += "&amp;"; else if (c == '<') o += "&lt;";
    else if (c == '>') o += "&gt;"; else if (c == '"') o += "&quot;";
    else o += c;
  }
  return o;
}

static String portalPage() {
  String p =
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>Ragnar CYD setup</title><style>"
    "body{font-family:system-ui,sans-serif;background:#0f172a;color:#e5e7eb;margin:0;padding:20px}"
    ".c{max-width:440px;margin:0 auto}h1{font-size:20px}label{display:block;margin:12px 0 4px;font-size:14px;color:#94a3b8}"
    "input{width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;color:#e5e7eb;border-radius:8px;padding:10px;font-size:15px}"
    "button{margin-top:18px;width:100%;background:#0284c7;color:#fff;border:0;border-radius:8px;padding:12px;font-size:16px}"
    "p{color:#94a3b8;font-size:13px}</style></head><body><div class='c'>"
    "<h1>Ragnar CYD node setup</h1>"
    "<p>Join this node to your WiFi and point it at your Ragnar. The device token comes from Ragnar → Config → CYD Nodes.</p>"
    "<form method='POST' action='/save'>"
    "<label>WiFi SSID (2.4 GHz)</label><input name='ssid' value='" + htmlAttr(g_cfg.ssid) + "'>"
    "<label>WiFi password</label><input name='pass' type='password' value='" + htmlAttr(g_cfg.pass) + "'>"
    "<label>Ragnar URL</label><input name='url' placeholder='http://192.168.1.50:8080' value='" + htmlAttr(g_cfg.url) + "'>"
    "<label>Device token</label><input name='token' value='" + htmlAttr(g_cfg.token) + "'>"
    "<label>Node name</label><input name='name' value='" + htmlAttr(g_cfg.name) + "'>"
    "<button type='submit'>Save &amp; reboot</button></form></div></body></html>";
  return p;
}

static void handlePortalRoot() { g_portalServer.send(200, "text/html", portalPage()); }

static void handlePortalSave() {
  RuntimeConfig c;
  c.ssid  = g_portalServer.arg("ssid");
  c.pass  = g_portalServer.arg("pass");
  c.url   = g_portalServer.arg("url");
  c.token = g_portalServer.arg("token");
  c.name  = g_portalServer.arg("name");
  // Trim a trailing slash on the URL so our path concatenation stays correct.
  while (c.url.endsWith("/")) c.url.remove(c.url.length() - 1);
  saveConfig(c);
  g_portalServer.send(200, "text/html",
    "<html><body style='font-family:system-ui,sans-serif;background:#0f172a;color:#e5e7eb;padding:24px'>"
    "<h2>Saved. Rebooting…</h2></body></html>");
  delay(800);
  ESP.restart();
}

static void drawPortalScreen(const String &ip) {
  gfx->fillScreen(gfx->color565(10, 12, 16));
  gfx->setTextColor(gfx->color565(90, 180, 255));
  gfx->setTextSize(2);
  gfx->setCursor(10, 16); gfx->print("SETUP MODE");
  gfx->setTextSize(1);
  gfx->setTextColor(gfx->color565(150, 160, 170));
  int16_t y = 60;
  gfx->setCursor(10, y); gfx->print("1) Join WiFi:"); y += 16;
  gfx->setTextColor(WHITE); gfx->setTextSize(2);
  gfx->setCursor(16, y); gfx->print(CYD_SETUP_AP_SSID); y += 26;
  gfx->setTextSize(1); gfx->setTextColor(gfx->color565(150, 160, 170));
  gfx->setCursor(16, y); gfx->print("pass: "); gfx->print(CYD_SETUP_AP_PASS); y += 26;
  gfx->setCursor(10, y); gfx->print("2) Open in a browser:"); y += 16;
  gfx->setTextColor(WHITE); gfx->setTextSize(2);
  gfx->setCursor(16, y); gfx->print("http://"); gfx->print(ip); y += 30;
  gfx->setTextSize(1); gfx->setTextColor(gfx->color565(120, 130, 140));
  gfx->setCursor(10, y); gfx->print("Fill WiFi + Ragnar URL + token,");  y += 14;
  gfx->setCursor(10, y); gfx->print("save, and the node reboots.");
}

// Raise the SoftAP + captive portal and serve requests until a save reboots us.
static void runConfigPortal() {
  WiFi.mode(WIFI_AP);
  const char *pw = strlen(CYD_SETUP_AP_PASS) >= 8 ? CYD_SETUP_AP_PASS : nullptr;
  WiFi.softAP(CYD_SETUP_AP_SSID, pw);
  IPAddress ip = WiFi.softAPIP();
  g_portalDNS.start(53, "*", ip);
  g_portalServer.on("/", handlePortalRoot);
  g_portalServer.on("/save", HTTP_POST, handlePortalSave);
  g_portalServer.onNotFound(handlePortalRoot);   // captive: any URL -> the form
  g_portalServer.begin();
  setStatus("setup portal", gfx->color565(230, 170, 50));
  drawPortalScreen(ip.toString());
  for (;;) {
    g_portalDNS.processNextRequest();
    g_portalServer.handleClient();
    delay(5);
  }
}
#endif // !CYD_TRANSPORT_SERIAL

// ════════════════════════════════════════════════════════════════════════════
//  Lifecycle
// ════════════════════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(CYD_SERIAL_BAUD);

  pinMode(PIN_LED_R, OUTPUT); pinMode(PIN_LED_G, OUTPUT); pinMode(PIN_LED_B, OUTPUT);
  digitalWrite(PIN_LED_R, HIGH); digitalWrite(PIN_LED_G, HIGH); digitalWrite(PIN_LED_B, HIGH); // off (active LOW)

  pinMode(TFT_BL, OUTPUT); digitalWrite(TFT_BL, HIGH);

  gfx->begin();
  gfx->fillScreen(BLACK);

  // Touch bus + CS/IRQ
  pinMode(TOUCH_CS, OUTPUT); digitalWrite(TOUCH_CS, HIGH);
  pinMode(TOUCH_IRQ, INPUT);
  touchSPI.begin(TOUCH_SCLK, TOUCH_MISO, TOUCH_MOSI, TOUCH_CS);

  loadConfig();   // node name (+ optional WiFi seeds) + BLE/backlight settings
  applyBacklight();
#if CYD_TRANSPORT_SERIAL
  Serial.setTimeout(20);   // cabled to the Pi; cyd_serial_bridge.py is the link
#else
  // WiFi transport: enter the setup portal if unconfigured or if BOOT is held.
  pinMode(PIN_BOOT_BUTTON, INPUT_PULLUP);
  bool forcePortal = (digitalRead(PIN_BOOT_BUTTON) == LOW);
  if (forcePortal || !haveConfig()) {
    runConfigPortal();   // never returns — reboots on save
  }
#endif

  setStatus("init BLE/WiFi", WHITE);
  render();

#if CYD_ENABLE_BLE
  BLEDevice::init("");
  g_bleReady = true;
#endif

  WiFi.mode(WIFI_STA);   // start the radio so promiscuous works later
  setStatus("ready", gfx->color565(70,200,120));
  g_needRedraw = true;
}

// One UI service step: drain serial, read touch, render if dirty. Called from
// every wait loop (sync, sniff dwell, BLE wait) so touch/display never stall.
static void serviceUI() {
#if CYD_TRANSPORT_SERIAL
  serialDrain();   // keep the display current with the Pi's status pushes
#endif
  static uint32_t lastTap = 0;
  int16_t px, py;
  if (touchRead(px, py) && millis() - lastTap > 250) {
    lastTap = millis();
    handleTouch(px, py);
  }
  if (g_needRedraw) render();
}

// Service the UI for `ms` (touch stays responsive across long radio phases).
static void pollTouchFor(uint32_t ms) {
  uint32_t start = millis();
  while (millis() - start < ms) { serviceUI(); delay(12); }
}

void loop() {
  // ── 0) WATERFALL MODE ───────────────────────────────────────────────────────
  // While the Waterfall screen is open, dedicate the loop to streaming spectrum
  // (skip the sniff/BLE windows) so it stays live. Tell Ragnar to stop the SDR
  // when the screen closes.
  static bool wasWf = false;
#if CYD_TRANSPORT_SERIAL
  if (g_wfActive) {
    serialSendWfReq(true);
    wasWf = true;
    pollTouchFor(1500);                  // drains wf frames, renders, handles touch
    return;
  }
  if (wasWf) { serialSendWfReq(false); wasWf = false; }
#endif

  // The LED is a STEADY link indicator, not a per-phase blinker (the old
  // per-phase toggling was the "LED twitch"). Solid blue = linked/running.
  digitalWrite(PIN_LED_R, HIGH); digitalWrite(PIN_LED_G, HIGH);
  digitalWrite(PIN_LED_B, LOW);

  // ── 1) SYNC WITH RAGNAR ─────────────────────────────────────────────────────
#if CYD_TRANSPORT_SERIAL
  // Cabled transport: push counts, flush queued actions, read pushed status.
  serialSendIngest();
  { String a; while (actionDequeue(a)) serialSendAction(a); }
  serialDrain();
  setStatus("usb-serial", colGreen());   // only redraws if the text changed
  pollTouchFor(CYD_SYNC_WINDOW_MS);       // responsive; renders only on change
#else
  setStatus("connecting wifi", colAmber());
  serviceUI();
  if (wifiConnect()) {
    httpPostIngest();
    httpGetStatus();
    String a;
    while (actionDequeue(a)) httpPostAction(a);
    setStatus(g_rs.ok ? "online" : "sync failed", g_rs.ok ? colGreen() : colRed());
    pollTouchFor(CYD_SYNC_WINDOW_MS);
  } else {
    setStatus("wifi unavailable", colRed());
    g_rs.ok = false;
    pollTouchFor(CYD_SYNC_WINDOW_MS);
  }
#endif

  // ── 2) WiFi promiscuous sweep — cooperative (services UI throughout) ─────────
  sniffWindow(CYD_SNIFF_WINDOW_MS);

  // ── 3) BLE advert scan — async; service UI while it runs (never blocks touch)─
#if CYD_ENABLE_BLE
  if (CYD_BLE_WINDOW_MS > 0) {
    bleStart(CYD_BLE_WINDOW_MS);
    uint32_t t0 = millis();
    while (g_bleBusy && millis() - t0 < (uint32_t)CYD_BLE_WINDOW_MS + 1500) {
      serviceUI(); delay(12);
    }
  }
#endif

  // Refresh the sensor-driven screens (SCAN/DEFEND/HOME) once per cycle, and only
  // when the counts actually changed — a real data update (~every sniff cycle),
  // not the every-2s status-push twitch.
  static uint32_t lastSensorSig = 0xFFFFFFFFu;
  uint32_t ss = (uint32_t)g_sc.beacons + ((uint32_t)g_sc.bssids << 9)
              + ((uint32_t)g_sc.deauths << 16) + ((uint32_t)g_sc.probes << 20)
              + ((uint32_t)g_sc.bleAdv << 25);
  if (ss != lastSensorSig) { lastSensorSig = ss; g_needRedraw = true; serviceUI(); }
}
