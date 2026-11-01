#!/usr/bin/env python
"""Read-only status check and optional charge test for a GoodWe inverter.

The optional write test switches the inverter to ECO_CHARGE (grid charging),
observes the battery for a while and always switches back to GENERAL mode.

Usage:
    python3 test.py 192.168.1.108
    python3 test.py 192.168.1.108 --family ES
    python3 test.py 192.168.1.108 --write --power 20 --soc 65 --hold 60
    python3 test.py 192.168.1.108 --e2e --power 20 --soc 65 --hold 60
"""

import argparse
import asyncio
import importlib.util
import os
import pathlib
import sys
import time
from datetime import datetime

import goodwe


def load_app_module():
    path = pathlib.Path(__file__).with_name("tibber-goodwe-charge.py")
    spec = importlib.util.spec_from_file_location("tibber_goodwe_charge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def print_status(status):
    if not status:
        print("No inverter status available.")
        return
    print(f"Operation mode : {status['operation_mode']}")
    print(f"Work mode      : {status['work_mode_label']} ({status['work_mode']})")
    print(f"Battery mode   : {status['battery_mode_label']} ({status['battery_mode']})")
    print(f"Battery SOC    : {status['battery_soc']}%")
    print(f"PV power       : {status['pv_power']}W")
    print(f"Battery power  : {status['battery_power']}W")
    print(f"Grid power     : {status['grid_power']}W")
    print(f"Load power     : {status['load_power']}W")
    print(f"ECO_CHARGE     : {status['eco_charge_supported']}, "
          f"target SOC: {status['target_soc_supported']}")


async def read_device_info(app, inverter_ip, inverter_family):
    inverter = await goodwe.connect(
        inverter_ip, family=inverter_family or None, timeout=2, retries=5
    )
    print(f"Model          : {inverter.model_name}")
    print(f"Serial number  : {inverter.serial_number}")
    print(f"Firmware       : {inverter.firmware} "
          f"(ARM {inverter.arm_version}, DSP1 {inverter.dsp1_version}, "
          f"DSP2 {inverter.dsp2_version})")

    modes = await inverter.get_operation_modes(include_emulated=True)
    mode_names = [m.name for m in modes]
    print(f"Supported modes: {mode_names}")
    print(f"ECO_CHARGE     : "
          f"{'yes' if 'ECO_CHARGE' in mode_names else 'no'}")
    target_support = ("yes (EcoMode V2)"
                      if app._supports_target_soc(inverter)
                      else "no (EcoMode V1, charges to BMS limit)")
    print(f"Target SOC     : {target_support}")

    for setting_id in ("work_mode", "eco_mode_1", "eco_mode_2_switch",
                       "eco_mode_3_switch", "eco_mode_4_switch"):
        try:
            value = await inverter.read_setting(setting_id)
            print(f"{setting_id:16}: {value}")
        except Exception as ex:
            print(f"{setting_id:16}: ERROR {ex!r}")


def run_e2e(app, args, status):
    """Run the real main() decision flow with a simulated Tibber price.

    Sequence: cheap -> ECO_CHARGE, cheap again -> stay ECO_CHARGE (hold),
    expensive -> GENERAL.
    """
    conf = app.Config.read()
    if not conf:
        print("No config found, cannot run end-to-end test.")
        return 1

    target_soc = args.soc
    if target_soc is None:
        target_soc = min(100, (status["battery_soc"] or 0) + 5)

    conf = dict(conf)
    conf.update({
        "inverter_ip": args.ip,
        "inverter_family": args.family,
        "target_soc": target_soc / 100.0,
        "price_start": 0.50,
        "price_stop": 0.51,
        "months": list(range(1, 13)),
        "start_hour": 0,
        "stop_hour": 24,
        "charge_power": args.power,
    })
    app.Config.read = lambda: conf

    cheap = {"total": 0.01, "energy": 0.0, "tax": 0.0, "startsAt": ""}
    expensive = {"total": 0.99, "energy": 0.0, "tax": 0.0, "startsAt": ""}

    print(f"\n--- E2E run 1: cheap price -> expect ECO_CHARGE "
          f"(power={args.power}%, target SOC={target_soc}%) ---")
    app.read_tibber_data = lambda home_id, pat: cheap
    app.run()

    try:
        deadline = time.time() + args.hold
        while time.time() < deadline:
            time.sleep(10)
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] while run 1:")
            print_status(app.get_inverter_status(args.ip, args.family))
    finally:
        print("\n--- E2E run 2: cheap price again -> expect stay ECO_CHARGE ---")
        app.read_tibber_data = lambda home_id, pat: cheap
        app.run()
        time.sleep(3)
        print_status(app.get_inverter_status(args.ip, args.family))

        print("\n--- E2E run 3: expensive price -> expect GENERAL ---")
        app.read_tibber_data = lambda home_id, pat: expensive
        app.run()
        time.sleep(8)
        print_status(app.get_inverter_status(args.ip, args.family))

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ip", help="inverter IP address")
    parser.add_argument("--family", default=None,
                        help="force inverter family, e.g. ES (default: auto detect)")
    parser.add_argument("--write", action="store_true",
                        help="run a real ECO_CHARGE test (writes to the inverter)")
    parser.add_argument("--e2e", action="store_true",
                        help="run the main decision flow with simulated Tibber "
                             "prices (writes to the inverter)")
    parser.add_argument("--power", type=int, default=20,
                        help="charge power in %% for the write test (default: 20)")
    parser.add_argument("--soc", type=int, default=None,
                        help="target SOC in %% (default: current SOC + 5)")
    parser.add_argument("--hold", type=int, default=60,
                        help="seconds to stay in ECO_CHARGE mode (default: 60)")
    args = parser.parse_args()

    # make sure Config.read() finds tibber-goodwe-charge.ini next to this script
    os.chdir(pathlib.Path(__file__).resolve().parent)

    app = load_app_module()

    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} "
          f"Reading inverter at {args.ip}")
    try:
        asyncio.run(read_device_info(app, args.ip, args.family))
    except Exception as ex:
        print(f"Could not read device info: {ex!r}")

    print("\n--- Initial status ---")
    status = None
    for _ in range(3):
        status = app.get_inverter_status(args.ip, args.family)
        if status is not None:
            break
        time.sleep(2)
    if status is None:
        print("Inverter is not reachable via the goodwe protocol.")
        sys.exit(1)

    print("\n--- Charge decision flag (simulated) ---")
    conf = app.Config.read()
    if not conf:
        print("No config found, skipping flag simulation.")
    else:
        real_now = datetime.now()
        test_month = (real_now.month if real_now.month in conf["months"]
                      else conf["months"][0])
        test_now = datetime(real_now.year, test_month, 15, conf["start_hour"], 0)
        soc = status["battery_soc"] if status["battery_soc"] is not None else 0
        mode = status["operation_mode"] or ""
        between = (conf["price_start"] + conf["price_stop"]) / 2

        scenarios = [
            ("cheap, GENERAL", test_now, conf["price_start"] - 0.01, "GENERAL"),
            ("cheap, already ECO_CHARGE", test_now, conf["price_stop"],
             "ECO_CHARGE"),
            ("between start/stop, GENERAL", test_now, between, "GENERAL"),
            ("between start/stop, ECO_CHARGE", test_now, between, "ECO_CHARGE"),
            ("expensive", test_now, conf["price_stop"] + 0.01, mode),
            ("outside charging window",
             test_now.replace(hour=conf["stop_hour"] % 24), 0.0, "GENERAL"),
            ("negative price, in window", test_now, -0.05, "GENERAL"),
        ]
        for name, when, price, scenario_mode in scenarios:
            flag = app.calculate_should_load(price, when, conf, scenario_mode)
            print(f"{name:32} price={price:5.2f} "
                  f"mode={scenario_mode:<10} -> should_load={flag}")
        print(f"(current SOC is {soc}%, target={conf['target_soc']:.0%}; "
              f"SOC no longer affects the decision)")

    if args.e2e:
        sys.exit(run_e2e(app, args, status))

    if not args.write:
        print("\nRead-only mode. Use --write to test ECO_CHARGE against the inverter.")
        return

    target_soc = args.soc
    if target_soc is None:
        target_soc = min(100, (status["battery_soc"] or 0) + 5)

    print(f"\n--- Setting ECO_CHARGE (power={args.power}%, "
          f"target SOC={target_soc}%, hold={args.hold}s) ---")
    if not app.start_loading(args.ip, args.family, args.power, target_soc):
        print("Could not set ECO_CHARGE mode.")
        sys.exit(1)

    try:
        deadline = time.time() + args.hold
        while time.time() < deadline:
            time.sleep(10)
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] while charging:")
            print_status(app.get_inverter_status(args.ip, args.family))
    finally:
        print("\n--- Setting back to GENERAL ---")
        app.stop_loading(args.ip, args.family)
        time.sleep(3)
        print_status(app.get_inverter_status(args.ip, args.family))

    print("\n--- Test complete ---")


if __name__ == "__main__":
    main()
