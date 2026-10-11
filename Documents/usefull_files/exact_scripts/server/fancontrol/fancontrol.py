#!/usr/bin/env python3
import signal
import subprocess
import sys
import time
from pathlib import Path

# Curves: (temperature °C, pwm 0-255), linear between points.
CPU_CURVE = [(50, 70), (55, 145), (60, 255)]
CPU_OFF_TEMP = 45      # once running, stay at minimum until below this
DISK_CURVE = [(45, 70), (50, 145), (60, 255)]
DISK_OFF_TEMP = 40

MIN_PWM = 70           # lowest pwm the fan keeps spinning at
KICK_PWM = 128         # 50%, used for 1 s when starting from standstill
RAMP_DOWN_STEP = 10    # max pwm decrease per loop; increases are immediate
INTERVAL_SEC = 5

HWMON = Path("/sys/class/hwmon")
THERMAL = Path("/sys/class/thermal")


def read(path):
    return path.read_text().strip()


def hwmon_dirs(name):
    return [p.parent for p in HWMON.glob("hwmon*/name") if read(p) == name]


def max_temp(paths):
    temps = []
    for p in paths:
        try:
            temps.append(int(read(p)) / 1000)
        except (OSError, ValueError):
            pass  # sensor unavailable (?)
    return max(temps, default=None)


def curve(temp, points, off_temp, running):
    if temp is None or temp < points[0][0]:
        # turn off if below the curve, unless already running and not yet below off_temp
        return points[0][1] if running and temp is not None and temp > off_temp else 0
    for (t0, p0), (t1, p1) in zip(points, points[1:]):
        if temp <= t1:
            return round(p0 + (p1 - p0) * (temp - t0) / (t1 - t0))
    return points[-1][1]


subprocess.run(["modprobe", "pwm_fan"], check=False)
subprocess.run(["modprobe", "drivetemp"], check=False)

# Wait for hwmon
for _ in range(20):
    fans = hwmon_dirs("pwmfan")
    if fans:
        break
    time.sleep(0.5)
else:
    sys.exit("pwm-fan hwmon device not found")
pwm = fans[0] / "pwm1"

enable = fans[0] / "pwm1_enable"
if enable.exists():
    enable.write_text("1")

zones = list(THERMAL.glob("thermal_zone*"))
core_temps = [z / "temp" for z in zones if read(z / "type") in ("cpu-thermal", "gpu-thermal")]

# Zones with the fan bound as a cooling device (cdevN (cooling device N) is a symlink to its directory)
fan_zones = [z for z in zones
             if any(c.is_dir() and read(c / "type") == "pwm-fan" for c in z.glob("cdev[0-9]*"))]
for z in fan_zones:
    (z / "policy").write_text("user_space")
    print(f"{z}: policy -> user_space", flush=True)

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
current = int(read(pwm))

try:
    while True:
        core = max_temp(core_temps)
        disk = max_temp([d / "temp1_input" for d in hwmon_dirs("drivetemp")])
        running = current > 0

        if core is None:
            target = 255  # can't read CPU/GPU temperature: failsafe
        else:
            target = max(curve(core, CPU_CURVE, CPU_OFF_TEMP, running),
                         curve(disk, DISK_CURVE, DISK_OFF_TEMP, running))

        if target < current:
            target = max(target, current - RAMP_DOWN_STEP)  # slow down gradually
            if target < MIN_PWM:
                target = 0

        if target != current:
            if current == 0 and target < KICK_PWM:
                pwm.write_text(str(KICK_PWM))  # kick-start from standstill
                time.sleep(1)
            pwm.write_text(str(target))
            print(f"core {core}, disks {disk} (°C): pwm {current} -> {target}", flush=True)
            current = target

        time.sleep(INTERVAL_SEC)
finally:
    for z in fan_zones:
        (z / "policy").write_text("step_wise")
        print(f"{z}: policy -> step_wise", flush=True)
