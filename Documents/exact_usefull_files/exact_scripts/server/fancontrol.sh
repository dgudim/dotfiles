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

# Music stuff
# 49000 - 3789 Hz
# 49100 - 3337 Hz
# 49200 - 2862 Hz
# 49450 - 2281 Hz
# 49400 - 1249 Hz
export D4=49400
export D5=49000
export A4=49100
export Ab4=49200
export G4=49200
export F4=49400
export C4_mid=49450

export sleep1=0.0625
export sleep2=0.125
export sleep3=0.1875
export sleep4=0.31

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
        sleep 7
    fi
    echo 30000000 > period && sleep 0.1
    echo $1 > duty_cycle && sleep 0.1
}

full() {
    set_speed 30000000
}

normal() {
    set_speed 23000000
}

idle() {
    set_speed 10150000
}


echo 0 > duty_cycle && sleep 3
echo 50000 > period && sleep 3

echo $D4 > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep1
echo $D4 > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep1
echo $D5 > duty_cycle && sleep $sleep2
echo 0 > duty_cycle && sleep $sleep2
echo $A4 > duty_cycle && sleep $sleep2
echo 0 > duty_cycle && sleep $sleep3
echo $Ab4 > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep2
echo $G4 > duty_cycle && sleep $sleep2
echo 0 > duty_cycle && sleep $sleep2
echo $F4 > duty_cycle && sleep $sleep2
echo 0 > duty_cycle && sleep $sleep2
echo $D4 > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep1
echo $F4 > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep1
echo $G4 > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep1
echo $C4_mid > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep 0.5

echo "Bootup sound complete, testing fan"

full
sleep 10
normal
sleep 10
idle
sleep 10
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


