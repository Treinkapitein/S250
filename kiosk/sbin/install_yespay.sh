#! /bin/sh

echo "Software downloading. It will take a few minutes, please wait."
wget --timeout=64 --tries=3 -c http://update.cereson.com/~update/yespay/YESEFT.tar.gz -O /tmp/YESEFT.tar.gz

cd /tmp
tar zxvf YESEFT.tar.gz
cp -r YESEFT /home/mm

export YESPAY_HOME=/home/mm/YESEFT
export JAVA_HOME=$YESPAY_HOME/jre1.6.0_17
export PATH=$JAVA_HOME/bin:$PATH

echo "Set up the MID and TID"
cd $YESPAY_HOME
bash EMBOSS-Setup.sh

