UUID="4896-E50E"
printf "\x${UUID:7:2}\x${UUID:5:2}\x${UUID:2:2}\x${UUID:0:2}" |
    dd bs=1 seek=67 count=4 conv=notrunc of=/dev/nvme0n1p1

# https://unix.stackexchange.com/questions/12858/how-to-change-filesystem-uuid-2-same-uuid
