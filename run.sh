#!/bin/sh

cd /home/pi/share/goodash
. venv/bin/activate
python app.py > run.log
