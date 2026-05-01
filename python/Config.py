#!/usr/bin/env python

import configparser
import os

# read config
config = configparser.ConfigParser()


def read():
    try:
        # read config
        config.read('tibber-goodwe-loading.ini')

        values = {}

        values["home_id"] = config['TibberSection']['home_id']
        values["pat"] = config['TibberSection']['pat']
        if os.getenv('HOME_ID', 'None') != 'None':
            values["home_id"] = os.getenv('HOME_ID')
        if os.getenv('PAT', 'None') != 'None':
            values["pat"] = os.getenv('PAT')

        values["inverter_ip"] = config['GoodweSection']['inverter_ip']
        if os.getenv('INVERTER_IP', 'None') != 'None':
            values["inverter_ip"] = os.getenv('INVERTER_IP')
            # print ("using env: INVERTER_IP")

        values["battery_soc_start"] = config['Limits']['battery_soc_start']
        values["battery_soc_stop"] = config['Limits']['battery_soc_stop']
        values["price_start"] = config['Limits']['price_start']
        values["price_stop"] = config['Limits']['price_stop']
        values["months"] = [int(m.strip()) for m in config['Limits']['months'].split(',')]
        values["start_hour"] = config['Limits']['start_hour']
        values["stop_hour"] = config['Limits']['stop_hour']
        if os.getenv('BATTERY_SOC_START', 'None') != 'None':
            values["battery_soc_start"] = float(os.getenv('BATTERY_SOC_START'))
        if os.getenv('BATTERY_SOC_STOP', 'None') != 'None':
            values["battery_soc_stop"] = float(os.getenv('BATTERY_SOC_STOP'))
        if os.getenv('PRICE_START', 'None') != 'None':
            values["price_start"] = float(os.getenv('PRICE_START'))
        if os.getenv('PRICE_STOP', 'None') != 'None':
            values["price_stop"] = float(os.getenv('PRICE_STOP'))
        if os.getenv('MONTHS', 'None') != 'None':
            values["months"] = [int(m.strip()) for m in os.getenv('MONTHS').split(',')]
            # print ("using env: MONTHS")
        if os.getenv('START_HOUR', 'None') != 'None':
            values["start_hour"] = os.getenv('START_HOUR')
            # print ("using env: START_HOUR")
        if os.getenv('STOP_HOUR', 'None') != 'None':
            values["stop_hour"] = os.getenv('STOP_HOUR')
            # print ("using env: STOP_HOUR")

        # print (datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " config: ", values)

        return values
    except Exception as ex:
        print("ERROR Config: ", ex)
