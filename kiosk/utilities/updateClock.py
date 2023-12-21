#!/bin/bash
echo "howcute121" | sudo -S sh -c "ntpdate pool.ntp.org"
sudo -K
echo "howcute121" | sudo -S sh -c "/sbin/hwclock --systohc"
echo "All Set!"
