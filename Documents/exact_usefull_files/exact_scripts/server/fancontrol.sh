#!/usr/bin/env bash

set -e

export OFF_TEMP=45
export ON_TEMP_IDLE=50
export ON_TEMP_NORMAL=55
export ON_TEMP_FULL=60

export OFF_HDD_TEMP=40
export ON_HDD_TEMP_IDLE=45
export ON_HDD_TEMP_NORMAL=50
export ON_HDD_TEMP_FULL=60

export DELAY_AFTER_ON_SEC=60


modprobe -r pwm_fan
modprobe drivetemp

echo "Loaded/unloaded kernel modules"

cd /sys/class/pwm/pwmchip1 || exit
echo 0 > "export" || true
echo "Exported pwm control channel 0"
cd pwm0 || exit

echo 1 > enable || true
echo "Enabled pwm control"

off() {
    echo 0 > duty_cycle && sleep 0.1
}

set_speed() {
    echo "Set speed to $1"
    if [ $(cat duty_cycle) -ne $1 ]; then
        off
        sleep 3
    fi
    echo 30000000 > period && sleep 0.1
    echo $1 > duty_cycle && sleep 0.1
}

full() {
    set_speed 30000000
}

normal() {
    set_speed 17000000
}

idle() {
    set_speed 7840000
}

full
sleep 5
normal
sleep 5
idle
sleep 5
off

get_temp() {
    sensors $1 | grep temp1 | cut -d' ' -f9 | cut -d '.' -f1 | cut -d '+' -f2
}

max() {
    echo $(($1>$2 ? $1 : $2))
}

while true
do
  cpu_temp=$(get_temp cpu_thermal-virtual-0)
  gpu_temp=$(get_temp gpu_thermal-virtual-0)
  core_temp=$(max $gpu_temp $cpu_temp)

  drive1_temp=$(get_temp drivetemp-scsi-0-0)
  drive2_temp=$(get_temp drivetemp-scsi-1-0)
  drive3_temp=$(get_temp drivetemp-scsi-2-0)
  drive4_temp=$(get_temp drivetemp-scsi-3-0)

  drive12_temp=$(max $drive1_temp $drive2_temp)
  drive34_temp=$(max $drive3_temp $drive4_temp)

  drive_temp=$(max $drive12_temp $drive34_temp)

  if [ $(( core_temp >= ON_TEMP_IDLE)) -eq 1 ] || [ $(( drive_temp >= ON_HDD_TEMP_IDLE )) -eq 1 ]; then
    echo "Core at $core_temp degrees, drives at $drive_temp degrees, turning on (idle)"
    idle
    sleep $DELAY_AFTER_ON_SEC
    continue
  fi

  if [ $(( core_temp >= ON_TEMP_NORMAL )) -eq 1 ] || [ $(( drive_temp >= ON_HDD_TEMP_NORMAL )) -eq 1 ]; then
    echo "Core at $core_temp degrees, drives at $drive_temp degrees, turning on (normal)"
    normal
    sleep $DELAY_AFTER_ON_SEC
    continue
  fi

  if [ $(( core_temp >= ON_TEMP_FULL )) -eq 1 ] || [ $(( drive_temp >= ON_HDD_TEMP_FULL )) -eq 1 ]; then
    echo "Core at $core_temp degrees, drives at $drive_temp degrees, turning on (FULL)"
    full
    sleep $DELAY_AFTER_ON_SEC
    continue
  fi

  if  [ $(( core_temp <= OFF_TEMP )) -eq 1 ] && [ $(( drive_temp <= OFF_HDD_TEMP )) -eq 1 ]; then
    if [ $(cat duty_cycle) -ne 0 ]; then
        echo "Core at $core_temp degrees, drives at $drive_temp degrees, turning off"
        off
    fi
  fi

  echo "Core at $core_temp degrees, drives at $drive_temp degrees"

  sleep 5
done


