# 49000 - 3789
# 49100 - 3337
# 49200 - 2862
# 49450 - 2281
# 49400 - 1249

export ON_TEMP=60
export OFF_TEMP=45
export ON_HDD_TEMP=48
export OFF_HDD_TEMP=40
export MIN_COOLING_TIME=300 # 5 minutes

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
if [ ! -f unexport ]
then
    echo 0 > "export"
    echo "Exported pwm control channel 0"
else
    echo "Pwm control already exported"
fi
cd pwm0 || exit

echo 1 > enable
echo "Enabled pwm control"

on() {
    echo 100 > period && sleep 0.1
    echo 70 > duty_cycle && sleep 0.1
}

off() {
    echo 100 > period && sleep 0.1
    echo 0 > duty_cycle && sleep 0.1
}

echo 50000 > period && sleep 3
echo 0 > duty_cycle && sleep 3

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
echo 0 > duty_cycle && sleep $sleep4
echo $C4_mid > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep4
echo $C4_mid > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep $sleep4
echo $C4_mid > duty_cycle && sleep $sleep1
echo 0 > duty_cycle && sleep 0.5

echo "Bootup sound complete, turning on the fan for 2.5 seconds"

on
sleep 2.5
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

  if (( drive_temp > ON_HDD_TEMP )); then
    echo "Drives at $drive12_temp degrees (> $ON_HDD_TEMP), turning on"
    on
    sleep $MIN_COOLING_TIME
    continue
  fi

  if (( core_temp > ON_TEMP )); then
    echo "Core at $core_temp degrees (> $ON_TEMP), turning on"
    on
    sleep $MIN_COOLING_TIME
    continue
  fi

  if  [ $(( core_temp <= OFF_TEMP )) -eq 1 ] && [ $(( drive_temp <= OFF_HDD_TEMP )) -eq 1 ]; then
    if [ $(cat duty_cycle) -ne 0 ]; then
        echo "Core at $core_temp degrees, drives at $drive_temp degrees, turning off"
        off
    fi
  fi

  sleep 5
done


