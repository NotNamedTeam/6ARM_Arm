# Манипулятор: FreeCAD, Gazebo и ESP32

- `robot_arm_gazebo/freecad/` — исходная сборка и отдельные детали FreeCAD.
- `robot_arm_gazebo/variants/` — варианты усиленных звеньев и лепилки. Последний сохранённый вариант — `labeler_mg90s_n20_v2`, с макетом N20 40 об/мин. Посадка лепилки непосредственно на вал MG90S ещё требует переделки.
- `robot_arm_gazebo/label_applicator/` — отдельные модели и предыдущие варианты лепилки.
- `robot_arm_gazebo/meshes/` и `robot_arm_gazebo/source/` — исходная геометрия, сведения об авторе и лицензия CC Attribution. Источник — BasementMaker, Thingiverse 4604664.
- `esp32_robot_arm_platformio/` — прошивка ESP32, скрипты и тесты калибровки. `esp32_robot_arm/` — исходный скетч Arduino.

## FreeCAD

Откройте `freecad/RobotArm_Assembly.FCStd` внутри нужного варианта через меню FreeCAD. Оставьте каталог `parts/` рядом со сборкой, чтобы FreeCAD нашёл связанные детали. Локальные скрипты, рассчитанные на распакованный AppImage, требуют настройки пути к FreeCAD на другом компьютере.

## Gazebo

На машине с ROS 2 Lyrical и Gazebo, из каталога `robot_arm_gazebo/variants/labeler_mg90s_n20_v2/`:

```bash
./open_gazebo.sh -r
```

Из второго терминала в том же каталоге:

```bash
./sim_control.sh apply-demo
```

Сцена и экспорт модели с мешами лежат в `export/`. Демонстрация выполняется в симуляции. Результаты приложенных проверок относятся к сохранённой конфигурации, геометрия посадки и работа реального механизма требуют проверки.

## ESP32

Для сборки откройте каталог `esp32_robot_arm_platformio/` в PlatformIO или запустите в нём `pio run`. Подключать ESP32 для сборки не требуется. Зависимости для консоли калибровки перечислены в `requirements-calibration.txt`.
