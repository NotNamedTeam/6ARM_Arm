#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>

// If WIFI_SSID is empty, ESP32 creates its own Wi-Fi network.
const char *WIFI_SSID = "";
const char *WIFI_PASSWORD = "";

const char *AP_SSID = "RobotArm-ESP32";
const char *AP_PASSWORD = "robotarm32";

// Pin order: base, shoulder, elbow, wrist tilt, wrist rotate, gripper.
// These defaults are intended for a classic ESP32 DevKit/WROOM.
const uint8_t SERVO_PINS[] = {13, 14, 16, 17, 18, 19};
const char *SERVO_NAMES[] = {
  "Основание", "Плечо", "Локоть", "Наклон кисти", "Поворот кисти", "Захват"
};
const uint8_t SERVO_COUNT = sizeof(SERVO_PINS) / sizeof(SERVO_PINS[0]);

// Start disabled so the arm cannot jump unexpectedly at power-on.
bool motorsEnabled = false;
int angles[] = {90, 90, 90, 90, 90, 45};
Servo servos[SERVO_COUNT];
WebServer server(80);

const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32 Robot Arm</title>
<style>
body{font:16px system-ui;background:#111827;color:#f3f4f6;max-width:680px;margin:auto;padding:20px}
h1{font-size:24px}.card{background:#1f2937;padding:18px;border-radius:14px;margin:12px 0}
.row{display:grid;grid-template-columns:145px 1fr 46px;gap:12px;align-items:center;margin:18px 0}
input{width:100%}button{border:0;border-radius:10px;padding:13px 18px;font-weight:700;cursor:pointer}
#enable{background:#10b981;color:#052e26}#stop{background:#ef4444;color:white;margin-left:8px}
.off{color:#fca5a5}.on{color:#6ee7b7}@media(max-width:520px){.row{grid-template-columns:1fr 52px}.row label{grid-column:1/3}}
</style></head><body><h1>Робот-манипулятор</h1>
<div class="card"><span id="state" class="off">Приводы выключены</span><br><br>
<button id="enable" onclick="setEnabled(1)">Включить</button><button id="stop" onclick="setEnabled(0)">СТОП</button></div>
<div class="card" id="controls"></div>
<script>
const names=['Основание','Плечо','Локоть','Наклон кисти','Поворот кисти','Захват'];
const initial=[90,90,90,90,90,45];
const box=document.getElementById('controls');
names.forEach((name,i)=>{box.insertAdjacentHTML('beforeend',`<div class="row"><label>${name}</label><input type="range" min="0" max="180" value="${initial[i]}" data-id="${i}"><output>${initial[i]}°</output></div>`)});
let timers={};
document.querySelectorAll('input').forEach(s=>s.oninput=()=>{s.nextElementSibling.value=s.value+'°';clearTimeout(timers[s.dataset.id]);timers[s.dataset.id]=setTimeout(()=>fetch(`/servo?id=${s.dataset.id}&angle=${s.value}`),35)});
function setEnabled(v){fetch('/enable?value='+v).then(()=>show(v));}
function show(v){const e=document.getElementById('state');e.textContent=v?'Приводы включены':'Приводы выключены';e.className=v?'on':'off';}
fetch('/status').then(r=>r.json()).then(x=>show(x.enabled));
</script></body></html>
)HTML";

void attachServos() {
  for (uint8_t i = 0; i < SERVO_COUNT; i++) {
    if (!servos[i].attached()) {
      servos[i].setPeriodHertz(50);
      servos[i].attach(SERVO_PINS[i], 500, 2500);
    }
    servos[i].write(angles[i]);
  }
  motorsEnabled = true;
}

void detachServos() {
  for (uint8_t i = 0; i < SERVO_COUNT; i++) servos[i].detach();
  motorsEnabled = false;
}

void handleServo() {
  if (!server.hasArg("id") || !server.hasArg("angle")) {
    server.send(400, "text/plain", "Missing id or angle");
    return;
  }
  int id = server.arg("id").toInt();
  int angle = constrain(server.arg("angle").toInt(), 0, 180);
  if (id < 0 || id >= SERVO_COUNT) {
    server.send(400, "text/plain", "Invalid servo id");
    return;
  }
  angles[id] = angle;
  if (motorsEnabled) servos[id].write(angle);
  server.send(200, "text/plain", "OK");
}

void handleEnable() {
  if (server.arg("value") == "1") attachServos();
  else detachServos();
  server.send(200, "text/plain", motorsEnabled ? "ON" : "OFF");
}

void startNetwork() {
  if (strlen(WIFI_SSID) > 0) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    unsigned long started = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) delay(250);
  }
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    Serial.print("Open http://");
    Serial.println(WiFi.softAPIP());
  } else {
    Serial.print("Open http://");
    Serial.println(WiFi.localIP());
  }
}

void setup() {
  Serial.begin(115200);
  startNetwork();
  server.on("/", []() { server.send_P(200, "text/html; charset=utf-8", PAGE); });
  server.on("/servo", handleServo);
  server.on("/enable", handleEnable);
  server.on("/status", []() {
    server.send(200, "application/json", String("{\"enabled\":") + (motorsEnabled ? "true" : "false") + "}");
  });
  server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
  server.begin();
  Serial.println("Web server started; motors are OFF.");
}

void loop() {
  server.handleClient();
  delay(2);
}
