#!/bin/bash
cd /app/python
# spread local GoodWe access when other tools poll the same dongle
sleep $((RANDOM % 11))
python3 tibber-goodwe-charge.py
