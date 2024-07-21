# 49000 - 3789
# 49100 - 3337
# 49200 - 2862
# 49450 - 2281
# 49400 - 1249

export D4=49400
export D5=49000
export A4=49100
export Ab4=49200
export G4=49450
export F4=49400
export C4_mid=49400

export sleep1=0.0625
export sleep2=0.125
export sleep3=0.1875
export sleep4=0.31

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

echo 100 > period && sleep 0.1
echo 60 > duty_cycle && sleep 0.1
