#! /bin/sh

DISPLAY=:0.0 xhost +
usermod -aG uucp mm

echo "make device of COM"
mknod /dev/ttyS4 c 188 0
mknod /dev/ttyS5 c 188 1
mknod /dev/ttyS6 c 188 2
echo "change the group for device of COM"
chgrp dialout /dev/ttyS4 /dev/ttyS5 /dev/ttyS6

echo "change the group for device of COM"
chmod g+w /dev/ttyS4 /dev/ttyS5 /dev/ttyS6 
chmod o-r /dev/ttyS4 /dev/ttyS5 /dev/ttyS6