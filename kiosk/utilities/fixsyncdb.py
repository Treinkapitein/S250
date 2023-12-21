#!/bin/bash
echo 'Backing up original DB'
cp ~/kiosk/var/db/sync.db ~/kiosk/var/db/sync.db.original
touch ~/kiosk/var/db/sync.db.fixed
rm ~/kiosk/var/db/sync.db.fixed
echo 'Rebuilding DB...'
sqlite3 ~/kiosk/var/db/sync.db '.dump' | sqlite3 ~/kiosk/var/db/sync.db.fixed
cp ~/kiosk/var/db/sync.db.fixed ~/kiosk/var/db/sync.db
echo 'All Done!'

