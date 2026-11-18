// ИНДИВИДУАЛЬНАЯ КАЛИБРОВКА. Меняйте настройки ниже и загружайте эту прошивку.
// Подоприте ВСЕ звенья: после теста удержание отключается, рука может упасть.
// После загрузки откройте Serial Monitor (115200, Newline) и отправьте GO.
// Во время включения/перезапуска НИ ОДИН привод сам не запускается.

#include <Arduino.h>
#include <ESP32Servo.h>
#include "config.h"

// ---------------------- МЕНЯТЬ ЗДЕСЬ ----------------------
constexpr int TEST_JOINT = 1;  // Начинаем со второго привода: плечо, GPIO17.
// Номер:                 0     1    2    3    4    5
int targetAngles[] = {    0,   87,  75,  30,  90,   0 };
//                       база плечо локоть кисть поворот захват
// GPIO:                 16    17    5   18   19   21
// Значения — абсолютные команды, а не приращения и не измеренные углы!
// GPIO19: 90 = стоп, 80..100 = скорость/направление, НЕ УГОЛ.
// Для основания сохранён диапазон команд 0..270, для остальных — 0..180.
// Это не подтверждённые механические пределы собранной руки.

constexpr unsigned long MOVE_WINDOW_MS = 1200;  // Время подачи сигнала, НЕ скорость.
constexpr bool HOLD_AFTER_MOVE = false;        // false: после теста выключить сигнал.
// ---------------------------------------------------------

static_assert(TEST_JOINT >= 0 && TEST_JOINT < static_cast<int>(SERVO_COUNT),
              "TEST_JOINT must be 0..5");
static_assert(sizeof(targetAngles) / sizeof(targetAngles[0]) == SERVO_COUNT,
              "Provide exactly six targets");
static_assert(MOVE_WINDOW_MS >= 100 && MOVE_WINDOW_MS <= 3000,
              "Use a short test window: 100..3000 ms");

namespace {
constexpr int ROTATION_AXIS = 4;
constexpr unsigned long ROTATION_MAX_MS = 250;
Servo servos[SERVO_COUNT];
int selectedJoint = TEST_JOINT;
int activeJoint = -1;
bool testRunning = false;
unsigned long testEndsAt = 0;

int angleToPulse(int id, int angle) {
  return map(angle, 0, MAX_ANGLES[id], SERVO_MIN_US, SERVO_MAX_US);
}

// Detach прекращает управляющие импульсы, но НЕ снимает питание сервопривода.
// Некоторые цифровые сервы могут сохранять удержание даже без импульсов.
void allOff() {
  if (servos[ROTATION_AXIS].attached()) {
    servos[ROTATION_AXIS].writeMicroseconds(angleToPulse(ROTATION_AXIS, 90));
    delay(60);  // Перед отключением GPIO19 отправить несколько импульсов нейтрали.
  }
  for (size_t i = 0; i < SERVO_COUNT; ++i) {
    if (servos[i].attached()) servos[i].detach();
    pinMode(SERVO_PINS[i], OUTPUT);
    digitalWrite(SERVO_PINS[i], LOW);
  }
  activeJoint = -1;
  testRunning = false;
}

bool validTarget(int id, int target) {
  if (id < 0 || id >= static_cast<int>(SERVO_COUNT)) return false;
  if (id == ROTATION_AXIS) return target >= 80 && target <= 100;
  return target >= 0 && target <= MAX_ANGLES[id];
}

void printStatus() {
  Serial.print("STATUS");
  for (size_t i = 0; i < SERVO_COUNT; ++i)
    Serial.printf(" %u:%d:%s", SERVO_PINS[i], targetAngles[i],
                  servos[i].attached() ? "ON" : "OFF");
  Serial.printf(" SELECTED=%d WINDOW_MS=%lu HOLD=%s\n", selectedJoint,
                MOVE_WINDOW_MS, HOLD_AFTER_MOVE ? "ON" : "OFF");
}

void startTest(int id, int target) {
  allOff();  // Никогда не включать сразу несколько приводов.
  if (!validTarget(id, target)) {
    Serial.println("ERR target: base 0..270; positional 0..180; GPIO19 80..100");
    return;
  }
  selectedJoint = id;
  targetAngles[id] = target;
  if (id == ROTATION_AXIS && target == 90) {
    Serial.println("GPIO19 NEUTRAL; all outputs OFF");
    return;
  }
  servos[id].setPeriodHertz(50);
  servos[id].attach(SERVO_PINS[id], SERVO_MIN_US, SERVO_MAX_US);
  if (!servos[id].attached()) {
    allOff();
    Serial.println("ERR attach; all outputs OFF");
    return;
  }
  servos[id].writeMicroseconds(angleToPulse(id, target));
  activeJoint = id;
  const unsigned long duration = id == ROTATION_AXIS
      ? min(MOVE_WINDOW_MS, ROTATION_MAX_MS) : MOVE_WINDOW_MS;
  testEndsAt = millis() + duration;
  testRunning = true;
  Serial.printf("TEST joint=%d GPIO=%u target=%d duration=%lu ms; others OFF\n",
                id, SERVO_PINS[id], target, duration);
}

void handleLine(String line) {
  line.trim();
  line.toUpperCase();
  if (line == "OFF" || line == "STOP") {
    allOff();
    Serial.println("OK ALL STOPPED");
  } else if (line == "GO" || line == "MOVE") {
    startTest(selectedJoint, targetAngles[selectedJoint]);
  } else if (line == "STATUS") {
    printStatus();
  } else {
    int id = -1, target = -1;
    if (sscanf(line.c_str(), "S %d %d", &id, &target) == 2) {
      startTest(id, target);  // Например, S 1 85: только плечо на 85°, потом OFF.
    } else if (sscanf(line.c_str(), "J %d", &id) == 1 &&
               id >= 0 && id < static_cast<int>(SERVO_COUNT)) {
      allOff();
      selectedJoint = id;
      printStatus();
    } else if (sscanf(line.c_str(), "T %d", &target) == 1 &&
               validTarget(selectedJoint, target)) {
      allOff();
      targetAngles[selectedJoint] = target;
      Serial.println("OK TARGET UPDATED; send GO to move");
    } else {
      Serial.println("ERR: GO, OFF, STATUS, J <0..5>, T <target>, S <id> <target>");
    }
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);
  allOff();
  Serial.println("MANUAL CALIBRATION READY; all outputs OFF; send GO to test one joint");
  printStatus();
}

void loop() {
  if (testRunning && static_cast<long>(millis() - testEndsAt) >= 0) {
    const int finishedJoint = activeJoint;
    testRunning = false;
    if (!HOLD_AFTER_MOVE || finishedJoint == ROTATION_AXIS) {
      allOff();
      Serial.println("TEST DONE; all outputs OFF (supply voltage still present)");
    } else {
      Serial.println("TEST DONE; only selected joint HOLD ON; send OFF to release");
    }
    printStatus();
  }
  if (Serial.available()) handleLine(Serial.readStringUntil('\n'));
  delay(1);
}
