#include <Arduino.h>
#include <ESP32Servo.h>
#include <WebServer.h>
#include <WiFi.h>
#include "config.h"

Servo servos[SERVO_COUNT];
int angles[SERVO_COUNT];
bool motorsEnabled = false;
WebServer server(80);
constexpr size_t CONTINUOUS_ROTATION_AXIS = 4;
constexpr int CONTINUOUS_ROTATION_STOP = 90;
constexpr unsigned long ROTATION_PULSE_MS = 700;
unsigned long rotationStopAt = 0;

const char PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32 Robot Arm</title><style>
body{font:16px system-ui;background:#111827;color:#f3f4f6;max-width:680px;margin:auto;padding:20px}
h1{font-size:24px}.card{background:#1f2937;padding:18px;border-radius:14px;margin:12px 0}
.row{display:grid;grid-template-columns:145px 1fr 46px;gap:12px;align-items:center;margin:18px 0}
input{width:100%}button{border:0;border-radius:10px;padding:13px 18px;font-weight:700;cursor:pointer}
#enable{background:#10b981;color:#052e26}#stop{background:#ef4444;color:white;margin-left:8px}
.off{color:#fca5a5}.on{color:#6ee7b7}@media(max-width:520px){.row{grid-template-columns:1fr 52px}.row label{grid-column:1/3}}
</style></head><body><h1>Робот-манипулятор</h1>
<div class="card"><span id="state" class="off">Приводы выключены</span><br><br>
<button id="enable" onclick="setEnabled(1)">Включить</button><button id="stop" onclick="setEnabled(0)">СТОП</button></div>
<div class="card" id="controls"></div><script>
const names=['Основание','Плечо','Локоть','Наклон кисти','Поворот захвата (90=стоп)','Захват'];
const initial=[0,82,75,30,90,0],limits=[270,180,180,180,180,180],box=document.getElementById('controls');
names.forEach((name,i)=>box.insertAdjacentHTML('beforeend',`<div class="row"><label>${name}</label><input type="range" min="0" max="${limits[i]}" value="${initial[i]}" data-id="${i}"><output>${initial[i]}°</output></div>`));
let timers={};document.querySelectorAll('input').forEach(s=>{
  s.oninput=()=>{s.nextElementSibling.value=s.value+'°';clearTimeout(timers[s.dataset.id]);timers[s.dataset.id]=setTimeout(()=>fetch(`/servo?id=${s.dataset.id}&angle=${s.value}`),35)};
  if(s.dataset.id==='4')s.onchange=()=>{clearTimeout(timers[4]);s.value=90;s.nextElementSibling.value='стоп';fetch('/servo?id=4&angle=90')};
});
function setEnabled(v){fetch('/enable?value='+v).then(()=>show(v))}function show(v){const e=document.getElementById('state');e.textContent=v?'Приводы включены':'Приводы выключены';e.className=v?'on':'off'}
fetch('/status').then(r=>r.json()).then(x=>show(x.enabled));
</script></body></html>
)HTML";

void writeServoPosition(size_t id) {
  if (id == 0) {
    const int pulse = map(angles[id], 0, MAX_ANGLES[id], SERVO_MIN_US, SERVO_MAX_US);
    servos[id].writeMicroseconds(pulse);
  } else {
    servos[id].write(angles[id]);
  }
}

void attachServos() {
  // A continuous-rotation servo must never be left driven by a position value.
  angles[CONTINUOUS_ROTATION_AXIS] = CONTINUOUS_ROTATION_STOP;
  rotationStopAt = 0;
  for (size_t i = 0; i < SERVO_COUNT; ++i) {
    if (i == CONTINUOUS_ROTATION_AXIS) continue;
    if (!servos[i].attached()) {
      servos[i].setPeriodHertz(50);
      servos[i].attach(SERVO_PINS[i], SERVO_MIN_US, SERVO_MAX_US);
    }
    writeServoPosition(i);
  }
  motorsEnabled = true;
  Serial.println("OK ENABLED");
}

void stopServos() {
  for (auto &servo : servos) servo.detach();
  angles[CONTINUOUS_ROTATION_AXIS] = CONTINUOUS_ROTATION_STOP;
  rotationStopAt = 0;
  motorsEnabled = false;
  Serial.println("OK STOPPED");
}

bool setServo(size_t id, int angle) {
  if (id >= SERVO_COUNT || angle < 0 || angle > MAX_ANGLES[id]) return false;
  angles[id] = angle;
  if (id == CONTINUOUS_ROTATION_AXIS) {
    if (angle == CONTINUOUS_ROTATION_STOP || !motorsEnabled) {
      servos[id].detach();
      rotationStopAt = 0;
    } else {
      if (!servos[id].attached()) {
        servos[id].setPeriodHertz(50);
        servos[id].attach(SERVO_PINS[id], SERVO_MIN_US, SERVO_MAX_US);
      }
      writeServoPosition(id);
      rotationStopAt = millis() + ROTATION_PULSE_MS;
    }
  } else if (motorsEnabled) {
    writeServoPosition(id);
  }
  return true;
}

void printStatus() {
  Serial.printf("STATUS %s", motorsEnabled ? "ENABLED" : "STOPPED");
  for (size_t i = 0; i < SERVO_COUNT; ++i) Serial.printf(" %d", angles[i]);
  Serial.println();
}

void handleSerialLine(String line) {
  line.trim();
  line.toUpperCase();
  if (line == "ENABLE") attachServos();
  else if (line == "STOP") stopServos();
  else if (line == "STATUS") printStatus();
  else {
    int id = -1, angle = -1;
    if (sscanf(line.c_str(), "S %d %d", &id, &angle) == 2 && setServo(id, angle))
      Serial.printf("OK S %d %d\n", id, angle);
    else
      Serial.println("ERR: use ENABLE, STOP, STATUS or S <id> <angle>");
  }
}

void setupWeb() {
  server.on("/", [] { server.send_P(200, "text/html; charset=utf-8", PAGE); });
  server.on("/servo", [] {
    if (!server.hasArg("id") || !server.hasArg("angle") ||
        !setServo(server.arg("id").toInt(), server.arg("angle").toInt())) {
      server.send(400, "text/plain", "Invalid id or angle");
      return;
    }
    server.send(200, "text/plain", "OK");
  });
  server.on("/enable", [] {
    server.arg("value") == "1" ? attachServos() : stopServos();
    server.send(200, "text/plain", motorsEnabled ? "ON" : "OFF");
  });
  server.on("/status", [] {
    server.send(200, "application/json", String("{\"enabled\":") +
                                           (motorsEnabled ? "true" : "false") + "}");
  });
  server.begin();
}

void setupNetwork() {
  if (strlen(WIFI_SSID)) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    const unsigned long started = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - started < 15000) delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WIFI http://"); Serial.println(WiFi.localIP());
  } else {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    Serial.print("AP http://"); Serial.println(WiFi.softAPIP());
  }
}

void setup() {
  Serial.begin(115200);
  for (size_t i = 0; i < SERVO_COUNT; ++i) angles[i] = START_ANGLES[i];
  setupNetwork();
  setupWeb();
  Serial.println("READY. Motors are OFF. Commands: ENABLE, STOP, STATUS, S <id> <angle>");
}

void loop() {
  server.handleClient();
  if (Serial.available()) handleSerialLine(Serial.readStringUntil('\n'));
  if (rotationStopAt && static_cast<long>(millis() - rotationStopAt) >= 0) {
    servos[CONTINUOUS_ROTATION_AXIS].detach();
    angles[CONTINUOUS_ROTATION_AXIS] = CONTINUOUS_ROTATION_STOP;
    rotationStopAt = 0;
    Serial.println("ROTATION AUTO-STOP");
  }
  delay(2);
}
