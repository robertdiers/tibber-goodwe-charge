#!/usr/bin/env python

from datetime import datetime
import requests
import socket
import goodwe

import Config


def is_valid_ip(ip):
    if not ip or len(str(ip).strip()) == 0:
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((str(ip), 8899))
        sock.close()
        return result == 0
    except Exception:
        return False


def read_tibber_data(home_id, pat):
    url = "https://api.tibber.com/v1-beta/gql"

    query = """
    query {
        viewer {
            home(id: "%s") {
                currentSubscription {
                    priceInfo {
                        current {
                            total
                            energy
                            tax
                            startsAt
                        }
                    }
                }
            }
        }
    }
    """ % home_id

    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json={"query": query}, headers=headers)
    data = response.json()

    if "errors" in data:
        print("Tibber API error:", data["errors"])
        return None

    if "data" in data and data["data"] and data["data"].get("viewer"):
        home = data["data"]["viewer"]["home"]
        if home and home.get("currentSubscription"):
            price_info = home["currentSubscription"]["priceInfo"]["current"]
            result = {
                "total": price_info["total"],
                "energy": price_info["energy"],
                "tax": price_info["tax"],
                "startsAt": price_info["startsAt"]
            }
            log_stmt = (f"Tibber: total={result['total']}, energy={result['energy']}, "
                        f"tax={result['tax']}, startsAt={result['startsAt']}")
            print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " " + log_stmt)
            return result

    return None


async def start_loading_async(inverter_ip):
    try:
        inverter = await goodwe.connect(inverter_ip)
        await inverter.set_operation_mode(goodwe.inverter.OperationMode.ECO_CHARGE)
        log_stmt = "Goodwe: Set to ECO_CHARGE mode (battery charging)"
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " " + log_stmt)
        return True
    except Exception as ex:
        print(f"ERROR starting battery load: {ex}")
        return False


def start_loading(inverter_ip):
    import asyncio
    return asyncio.run(start_loading_async(inverter_ip))


async def stop_loading_async(inverter_ip):
    try:
        inverter = await goodwe.connect(inverter_ip)
        await inverter.set_operation_mode(goodwe.inverter.OperationMode.GENERAL)
        log_stmt = "Goodwe: Set to GENERAL mode (normal operation)"
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " " + log_stmt)
        return True
    except Exception as ex:
        print(f"ERROR stopping battery load: {ex}")
        return False


def stop_loading(inverter_ip):
    import asyncio
    return asyncio.run(stop_loading_async(inverter_ip))


async def get_inverter_status_async(inverter_ip):
    try:
        inverter = await goodwe.connect(inverter_ip)
        operation_mode = await inverter.get_operation_mode()
        runtime_data = await inverter.read_runtime_data()

        status = {
            "operation_mode": operation_mode.name,
            "work_mode": runtime_data.get("work_mode"),
            "work_mode_label": runtime_data.get("work_mode_label"),
            "battery_mode": runtime_data.get("battery_mode"),
            "battery_mode_label": runtime_data.get("battery_mode_label"),
            "battery_soc": runtime_data.get("battery_soc"),
            "inverter": inverter
        }

        # normal output
        # operation_mode=GENERAL, work_mode=Normal (On-Grid), battery=Discharge, soc=98%

        log_stmt = (f"Goodwe: operation_mode={status['operation_mode']}, "
                    f"work_mode={status['work_mode_label']}, "
                    f"battery={status['battery_mode_label']}, "
                    f"soc={status['battery_soc']}%")
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " " + log_stmt)
        return status

    except Exception as ex:
        print(f"ERROR getting inverter status: {ex}")
        return None


def get_inverter_status(inverter_ip):
    import asyncio
    return asyncio.run(get_inverter_status_async(inverter_ip))


if __name__ == "__main__":
    # print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " START #####")
    try:
        conf = Config.read()

        # read Tibber API to get the actual price predictions
        tibber_data = read_tibber_data(conf["home_id"], conf["pat"])

        # stop if no valid data from tibber
        if not tibber_data:
            print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " no tibber data")
            exit(1)

        # check if inverter
        is_inverter_configured_and_available = (
            conf.get("inverter_ip") and
            len(str(conf["inverter_ip"]).strip()) > 0 and
            is_valid_ip(conf["inverter_ip"])
        )

        # read the actual inverter status
        if is_inverter_configured_and_available:
            inverter_status = get_inverter_status(conf["inverter_ip"])

        # we should calculate as flag and decide what to do
        should_load = 0

        # actual data
        now = datetime.now()
        actual_month_number = now.month  # 1 to 12 for Jan to Dec
        actual_hour = now.hour  # 0 to 23

        # if price is negative - full load - but at these times the batteries are already full...
        if tibber_data["total"] < 0:
            # full load we can earn money
            print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") +
                  f" negative price: {tibber_data['total']}")
        else:
            # we need to pay for energy from outside - need to decide if we should load or not
            # check the correct month - only during winter times
            if actual_month_number in conf["months"]:
                # check the actual time of the day
                if actual_hour >= conf["start_hour"] and actual_hour < conf["stop_hour"]:
                    # check the actual price for energy
                    if is_inverter_configured_and_available:
                        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") +
                              f" price={tibber_data['total']}, SOC={inverter_status['battery_soc']}%")
                        # Start charging: price <= price_start AND SOC < threshold
                        if tibber_data["total"] <= conf["price_start"]:
                            if inverter_status['battery_soc'] <= (100 * conf["battery_soc_start"]):
                                should_load = 1
                        # Keep charging: price <= price_stop AND SOC < threshold
                        if (tibber_data["total"] <= conf["price_stop"] and
                                'ECO_CHARGE' in inverter_status['operation_mode']):
                            if inverter_status['battery_soc'] <= (100 * conf["battery_soc_stop"]):
                                should_load = 1

        # send operating mode to inverter - this is a writing into the flash - to NOT write it all the time
        if is_inverter_configured_and_available:
            if should_load == 1 and 'GENERAL' in inverter_status['operation_mode']:
                start_loading(conf["inverter_ip"])
            if should_load == 0 and 'ECO_CHARGE' in inverter_status['operation_mode']:
                stop_loading(conf["inverter_ip"])

        # print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " END #####")

    except Exception as ex:
        print("ERROR: ", ex)
