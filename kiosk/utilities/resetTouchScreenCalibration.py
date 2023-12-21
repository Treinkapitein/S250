#!/bin/bash

# get the HDMI port
get_base_board_info()
{
    c=`echo 'howcute121' | sudo -S sh -c "dmidecode | grep -A8 \"Base Board Information$\" | grep \"Product Name\""`
    base_board=`echo $c | awk -F"Product Name: " '{print $2}'`
}

get_base_board_info

if [ "$base_board" = "DG45FC" ]; then
   HDMI_PORT="HDMI-1"
else
   HDMI_PORT="HDMI-2"
fi

echo -n "Be sure that an operator stands in front of the kiosk touch screen.(yes|no):"

read sure

if [ -z $sure ] || [ $sure != "yes" ] ; then
    exit 0
fi

cd /home/mm/kiosk/mkc2
./mkc.py stop

DISPLAY=:0.0 xrandr --output $HDMI_PORT --off

cd /elo
echo howcute121 |DISPLAY=:0.0 sudo -S ./elova -u


cd /home/mm/kiosk/mkc2
./mkc.py start


DISPLAY=:0.0 xrandr --output $HDMI_PORT --auto
DISPLAY=:0.0 xrandr --output VGA --left-of $HDMI_PORT
