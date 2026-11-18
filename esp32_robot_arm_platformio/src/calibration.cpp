#include <Arduino.h>
#include <ESP32Servo.h>
#include "config.h"

// Calibration firmware: every servo starts detached. Axes can remain attached
// while another is adjusted so that load-bearing joints do not sag.
// All commanded angles are absolute from that servo's zero.
Servo servos[SERVO_COUNT];
int angles[SERVO_COUNT] = {0, 82, 75, 30, 90, 0};
bool activeAxes[SERVO_COUNT] = {};

int angleToPulse(int id, int angle) {
  return map(angle, 0, MAX_ANGLES[id], SERVO_MIN_US, SERVO_MAX_US);
}

void stopAxis(int id) {
  if (activeAxes[id]) servos[id].detach();
  activeAxes[id] = false;
}

void stopAll() {
  for (size_t i = 0; i < SERVO_COUNT; ++i) stopAxis(i);
}

bool valid(int id, int angle) {
  return id >= 0 && id < static_cast<int>(SERVO_COUNT) &&
         angle >= 0 && angle <= MAX_ANGLES[id];
}

void attachAxis(int id, int angle) {
  angles[id] = angle;
  if (!activeAxes[id]) {
    servos[id].setPeriodHertz(50);
    servos[id].attach(SERVO_PINS[id], SERVO_MIN_US, SERVO_MAX_US);
  }
  activeAxes[id] = servos[id].attached();
  if (!activeAxes[id]) {
    Serial.printf("ERR ATTACH %d GPIO %u\n", id, SERVO_PINS[id]);
    return;
  }
  servos[id].writeMicroseconds(angleToPulse(id, angle));
  Serial.printf("OK ACTIVE %d GPIO %u ANGLE %d\n", id, SERVO_PINS[id], angle);
}

void handleLine(String line) {
  line.trim();
  line.toUpperCase();
  if (line == "STOP") {
    stopAll();
    Serial.println("OK ALL STOPPED");
    return;
  }
  int id = -1, angle = -1;
  if (sscanf(line.c_str(), "STOP %d", &id) == 1 &&
      id >= 0 && id < static_cast<int>(SERVO_COUNT)) {
    stopAxis(id);
    Serial.printf("OK STOPPED %d\n", id);
    return;
  }
  if (line == "STATUS") {
    Serial.print("STATUS");
    for (size_t i = 0; i < SERVO_COUNT; ++i)
      Serial.printf(" %u:%d:%s", SERVO_PINS[i], angles[i],
                    activeAxes[i] ? "ON" : "OFF");
    Serial.println();
    return;
  }
  if (sscanf(line.c_str(), "A %d %d", &id, &angle) == 2 && valid(id, angle)) {
    attachAxis(id, angle);
    return;
  }
  if (sscanf(line.c_str(), "S %d %d", &id, &angle) == 2 &&
      valid(id, angle) && activeAxes[id]) {
    angles[id] = angle;
    servos[id].writeMicroseconds(angleToPulse(id, angle));
    Serial.printf("OK S %d %d\n", id, angle);
    return;
  }
  Serial.println("ERR: A <id> <angle>, S <active-id> <angle>, STATUS, STOP [id]");
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(100);
  Serial.println("CALIBRATION READY; all servos OFF");
}

void loop() {
  if (Serial.available()) handleLine(Serial.readStringUntil('\n'));
  delay(2);
}
