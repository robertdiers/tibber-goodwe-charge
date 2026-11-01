#!/usr/bin/env python

from datetime import datetime
import asyncio
import requests
import goodwe

import Config


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


def _connect(inverter_ip, inverter_family=None):
    # family=None lets the library detect the inverter (ET/EH/BT/BH, ES/EM/BP, DT/...)
    # a few extra retries help with the sometimes flaky Wi-Fi/LAN dongle
    return goodwe.connect(
        inverter_ip,
        family=inverter_family or None,
        timeout=2,
        retries=5,
    )


async def _read_operation_mode(inverter):
    mode = await inverter.get_operation_mode()
    if mode is None:
        # Some ES devices return an unknown work_mode value on the first read
        mode = await inverter.get_operation_mode()
    return mode


def _supports_target_soc(inverter):
    """Answer whether the inverter can store a target SOC in its eco mode.

    EcoMode V1 (older firmware) accepts eco_mode_soc in the library API but
    silently ignores it and charges up to the BMS limit. goodwe 0.4.10 exposes
    this via a method on ES/EM/BP and a flag on ET/EH/BT/BH.
    """
    checker = getattr(inverter, "_supports_eco_mode_v2", None)
    if callable(checker):
        return bool(checker())
    return bool(getattr(inverter, "_has_eco_mode_v2", False))


async def start_loading_async(inverter_ip, inverter_family=None,
                              charge_power=100, target_soc=100):
    try:
        inverter = await _connect(inverter_ip, inverter_family)
        await inverter.set_operation_mode(
            goodwe.OperationMode.ECO_CHARGE,
            eco_mode_power=charge_power,
            eco_mode_soc=target_soc,
        )
        log_stmt = (f"Goodwe: Set to ECO_CHARGE mode "
                    f"(power={charge_power}%, target SOC={target_soc}%)")
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " " + log_stmt)
        return True
    except Exception as ex:
        print(f"ERROR starting battery load: {ex}")
        return False


def start_loading(inverter_ip, inverter_family=None,
                  charge_power=100, target_soc=100):
    return asyncio.run(start_loading_async(
        inverter_ip, inverter_family, charge_power, target_soc
    ))


async def stop_loading_async(inverter_ip, inverter_family=None):
    try:
        inverter = await _connect(inverter_ip, inverter_family)
        await inverter.set_operation_mode(goodwe.OperationMode.GENERAL)
        log_stmt = "Goodwe: Set to GENERAL mode (normal operation)"
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " " + log_stmt)
        return True
    except Exception as ex:
        print(f"ERROR stopping battery load: {ex}")
        return False


def stop_loading(inverter_ip, inverter_family=None):
    return asyncio.run(stop_loading_async(inverter_ip, inverter_family))


async def get_inverter_status_async(inverter_ip, inverter_family=None):
    try:
        inverter = await _connect(inverter_ip, inverter_family)
        supported_modes = [
            mode.name
            for mode in await inverter.get_operation_modes(include_emulated=True)
        ]
        eco_charge_supported = "ECO_CHARGE" in supported_modes
        target_soc_supported = _supports_target_soc(inverter)

        # DT/MS/NS/XS do not implement get_operation_mode(); skip it there so
        # that the status is still readable and the caller can disable writes.
        operation_mode = None
        if eco_charge_supported:
            operation_mode = await _read_operation_mode(inverter)

        runtime_data = await inverter.read_runtime_data()

        load_power = runtime_data.get("pload")
        if load_power is None:
            # ET/EH/BT/BH publish the load as house_consumption instead
            load_power = runtime_data.get("house_consumption")

        status = {
            "model_name": inverter.model_name,
            "serial_number": inverter.serial_number,
            "firmware": inverter.firmware,
            "supported_modes": supported_modes,
            "eco_charge_supported": eco_charge_supported,
            "target_soc_supported": target_soc_supported,
            "operation_mode": operation_mode.name if operation_mode is not None else None,
            "work_mode": runtime_data.get("work_mode"),
            "work_mode_label": runtime_data.get("work_mode_label"),
            "battery_mode": runtime_data.get("battery_mode"),
            "battery_mode_label": runtime_data.get("battery_mode_label"),
            "battery_soc": runtime_data.get("battery_soc"),
            "pv_power": runtime_data.get("ppv"),
            "battery_power": runtime_data.get("pbattery1"),
            "grid_power": runtime_data.get("pgrid"),
            "load_power": load_power,
        }

        # normal output
        # operation_mode=GENERAL, work_mode=Normal (On-Grid), battery=Discharge, soc=98%

        log_stmt = (f"Goodwe: operation_mode={status['operation_mode']}, "
                    f"work_mode={status['work_mode_label']}, "
                    f"battery={status['battery_mode_label']}, "
                    f"soc={status['battery_soc']}%, "
                    f"pv={status['pv_power']}W, "
                    f"battery={status['battery_power']}W, "
                    f"grid={status['grid_power']}W")
        print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " " + log_stmt)
        return status

    except Exception as ex:
        print(f"ERROR getting inverter status: {ex}")
        return None


def get_inverter_status(inverter_ip, inverter_family=None):
    return asyncio.run(get_inverter_status_async(inverter_ip, inverter_family))


def is_inverter_configured(conf):
    return bool(conf.get("inverter_ip")) and len(str(conf["inverter_ip"]).strip()) > 0


def calculate_should_load(tibber_total, now, conf, operation_mode):
    """Decide whether the inverter should charge. Side-effect free for testing.

    While the price is cheap and we are inside the month/hour window the inverter
    stays in ECO_CHARGE, even after the target SOC is reached. In that mode the ES
    battery does not discharge and the grid covers the load, so the battery is kept
    for the expensive hours. price_start enters, price_stop exits (hysteresis).
    """
    operation_mode = operation_mode or ""

    # only during the configured months
    if now.month not in conf["months"]:
        return 0

    # only during the configured time of the day
    if not (conf["start_hour"] <= now.hour < conf["stop_hour"]):
        return 0

    # Start charging on a cheap price
    if tibber_total <= conf["price_start"]:
        return 1

    # Keep charging until the price rises above price_stop
    if tibber_total <= conf["price_stop"] and "ECO_CHARGE" in operation_mode:
        return 1

    return 0


def run():
    # print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " START #####")
    try:
        conf = Config.read()
        if not conf:
            print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " no valid config")
            exit(1)

        # read Tibber API to get the actual price predictions
        tibber_data = read_tibber_data(conf["home_id"], conf["pat"])

        # stop if no valid data from tibber
        if not tibber_data:
            print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " no tibber data")
            exit(1)

        # check the inverter: a real protocol connection is the only reliable test
        # (the GoodWe dongle usually does not listen on TCP port 8899)
        inverter_status = None
        if is_inverter_configured(conf):
            inverter_status = get_inverter_status(
                conf["inverter_ip"], conf.get("inverter_family")
            )
        is_inverter_configured_and_available = inverter_status is not None
        eco_charge_supported = bool(
            inverter_status and inverter_status.get("eco_charge_supported")
        )
        target_soc_supported = bool(
            inverter_status and inverter_status.get("target_soc_supported")
        )

        # we should calculate as flag and decide what to do
        now = datetime.now()

        # target SOC written into the inverter's eco mode schedule. With EcoMode V2
        # firmware the inverter stops grid charging at this level, but it stays in
        # ECO_CHARGE (no discharge) until the price rises or the window ends.
        target_soc = max(0, min(100, int(round(100 * conf["target_soc"]))))

        should_load = 0
        if is_inverter_configured_and_available:
            operation_mode = inverter_status.get("operation_mode") or ""
            battery_soc = inverter_status.get("battery_soc")
            print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") +
                  f" price={tibber_data['total']}, SOC={battery_soc}%, "
                  f"mode={operation_mode}, "
                  f"target_soc_supported={target_soc_supported}")
            if not eco_charge_supported:
                print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") +
                      " Goodwe: ECO_CHARGE is not supported by this inverter "
                      f"(modes={inverter_status.get('supported_modes')}); "
                      "mode control disabled")
            else:
                should_load = calculate_should_load(
                    tibber_data["total"], now, conf, operation_mode
                )

        # send operating mode to inverter - this is a writing into the flash - to NOT write it all the time
        if eco_charge_supported:
            operation_mode = inverter_status.get("operation_mode") or ""
            if should_load == 1 and 'GENERAL' in operation_mode:
                if not target_soc_supported and target_soc < 100:
                    print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") +
                          " WARN: EcoMode V1 detected - the inverter ignores "
                          f"target SOC {target_soc}% and charges to the BMS limit")
                start_loading(
                    conf["inverter_ip"],
                    conf.get("inverter_family"),
                    conf["charge_power"],
                    target_soc,
                )
            if should_load == 0 and 'ECO_CHARGE' in operation_mode:
                stop_loading(conf["inverter_ip"], conf.get("inverter_family"))

        # print(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + " END #####")

    except Exception as ex:
        print("ERROR: ", ex)


if __name__ == "__main__":
    run()
