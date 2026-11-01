#!/usr/bin/env python

import configparser
import os

# read config
config = configparser.ConfigParser()


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=None):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def read():
    try:
        # read config
        config.read('tibber-goodwe-charge.ini')

        values = {}

        values["home_id"] = config['TibberSection']['home_id']
        values["pat"] = config['TibberSection']['pat']
        if os.getenv('HOME_ID', 'None') != 'None':
            values["home_id"] = os.getenv('HOME_ID')
        if os.getenv('PAT', 'None') != 'None':
            values["pat"] = os.getenv('PAT')

        values["inverter_ip"] = config['GoodweSection']['inverter_ip']
        values["inverter_family"] = config.get(
            'GoodweSection', 'family', fallback=''
        ).strip() or None
        if os.getenv('INVERTER_IP', 'None') != 'None':
            values["inverter_ip"] = os.getenv('INVERTER_IP')
            # print ("using env: INVERTER_IP")
        if os.getenv('INVERTER_FAMILY', 'None') != 'None':
            values["inverter_family"] = os.getenv('INVERTER_FAMILY').strip() or None

        values["target_soc"] = _to_float(config['Limits']['target_soc'], 0.50)
        values["price_start"] = _to_float(config['Limits']['price_start'], 0.23)
        values["price_stop"] = _to_float(config['Limits']['price_stop'], 0.26)
        values["months"] = [int(m.strip()) for m in config['Limits']['months'].split(',')]
        values["start_hour"] = _to_int(config['Limits']['start_hour'], 1)
        values["stop_hour"] = _to_int(config['Limits']['stop_hour'], 4)
        values["charge_power"] = _to_int(
            config.get('Limits', 'charge_power', fallback='100'), 100
        )
        if os.getenv('TARGET_SOC', 'None') != 'None':
            values["target_soc"] = _to_float(
                os.getenv('TARGET_SOC'), values["target_soc"]
            )
        if os.getenv('PRICE_START', 'None') != 'None':
            values["price_start"] = _to_float(
                os.getenv('PRICE_START'), values["price_start"]
            )
        if os.getenv('PRICE_STOP', 'None') != 'None':
            values["price_stop"] = _to_float(
                os.getenv('PRICE_STOP'), values["price_stop"]
            )
        if os.getenv('MONTHS', 'None') != 'None':
            values["months"] = [int(m.strip()) for m in os.getenv('MONTHS').split(',')]
            # print ("using env: MONTHS")
        if os.getenv('START_HOUR', 'None') != 'None':
            values["start_hour"] = _to_int(
                os.getenv('START_HOUR'), values["start_hour"]
            )
            # print ("using env: START_HOUR")
        if os.getenv('STOP_HOUR', 'None') != 'None':
            values["stop_hour"] = _to_int(
                os.getenv('STOP_HOUR'), values["stop_hour"]
            )
            # print ("using env: STOP_HOUR")
        if os.getenv('CHARGE_POWER', 'None') != 'None':
            values["charge_power"] = _to_int(
                os.getenv('CHARGE_POWER'), values["charge_power"]
            )

        # keep the inverter limits in a valid range
        values["target_soc"] = max(0.0, min(1.0, values["target_soc"]))
        values["charge_power"] = max(0, min(100, values["charge_power"]))

        # print (datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " config: ", values)

        return values
    except Exception as ex:
        print("ERROR Config: ", ex)
