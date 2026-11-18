#pragma once
#include <Arduino.h>

// Leave empty to make the ESP32 create its own Wi-Fi network.
constexpr char WIFI_SSID[] = "";
constexpr char WIFI_PASSWORD[] = "";

constexpr char AP_SSID[] = "RobotArm-ESP32";
constexpr char AP_PASSWORD[] = "robotarm32";

// base, shoulder, elbow, wrist tilt, wrist rotate, gripper
constexpr uint8_t SERVO_PINS[] = {16, 17, 5, 18, 19, 21};
constexpr int START_ANGLES[] = {0, 82, 75, 30, 90, 0};
constexpr int MAX_ANGLES[] = {270, 180, 180, 180, 180, 180};
constexpr size_t SERVO_COUNT = sizeof(SERVO_PINS) / sizeof(SERVO_PINS[0]);

constexpr int SERVO_MIN_US = 500;
constexpr int SERVO_MAX_US = 2500;
