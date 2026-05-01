#!/usr/bin/env python

import asyncio
import goodwe
from datetime import datetime


async def test_inverter(inverter_ip):
    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Testing inverter: {inverter_ip}")

    # 1. Read initial status
    print("\n--- Initial status ---")
    inverter = await goodwe.connect(inverter_ip)
    operation_mode = await inverter.get_operation_mode()

    # Check supported modes
    supported_modes = await inverter.get_operation_modes(include_emulated=True)
    print(f"Supported modes: {[m.name for m in supported_modes]}")
    runtime_data = await inverter.read_runtime_data()

    # Check eco mode settings
    try:
        eco_enable = await inverter.read_setting('eco_mode_enable')
        print(f"Eco mode enabled: {eco_enable}")
        eco_mode = await inverter.read_setting('eco_mode_1')
        print(f"Eco mode 1: {eco_mode}")
    except Exception as e:
        print(f"Could not read eco mode settings: {e}")

    print(f"Operation mode: {operation_mode.name}")
    print(f"Work mode: {runtime_data.get('work_mode_label')}")
    print(f"Battery mode: {runtime_data.get('battery_mode_label')}")
    print(f"Battery SOC: {runtime_data.get('battery_soc')}%")
    print(f"Battery power: {runtime_data.get('battery_power')}W")
    print(f"PV power: {runtime_data.get('pv_power')}W")
    print(f"Grid power: {runtime_data.get('grid_power')}W")

    # 2. Set to ECO_CHARGE
    print("\n--- Setting to ECO_CHARGE ---")
    await inverter.set_operation_mode(goodwe.inverter.OperationMode.ECO_CHARGE)
    print("Mode set to ECO_CHARGE")

    # Wait a bit for the mode to take effect
    await asyncio.sleep(5)

    # 3. Read status again
    print("\n--- Status after ECO_CHARGE ---")
    operation_mode = await inverter.get_operation_mode()
    runtime_data = await inverter.read_runtime_data()

    print(f"Operation mode: {operation_mode.name}")
    print(f"Work mode: {runtime_data.get('work_mode_label')}")
    print(f"Battery mode: {runtime_data.get('battery_mode_label')}")
    print(f"Battery SOC: {runtime_data.get('battery_soc')}%")
    print(f"Battery power: {runtime_data.get('battery_power')}W")
    print(f"PV power: {runtime_data.get('pv_power')}W")
    print(f"Grid power: {runtime_data.get('grid_power')}W")

    # Check if charging
    battery_mode = runtime_data.get("battery_mode_label")
    if battery_mode == "Charge":
        print("\n>>> Battery IS CHARGING!")
    else:
        print(f"\n>>> Battery is NOT charging (mode: {battery_mode})")

    # Wait a bit
    await asyncio.sleep(5)

    # 4. Set back to GENERAL
    print("\n--- Setting back to GENERAL ---")
    await inverter.set_operation_mode(goodwe.inverter.OperationMode.GENERAL)
    print("Mode set to GENERAL")

    # 5. Final status check
    await asyncio.sleep(5)
    print("\n--- Final status ---")
    operation_mode = await inverter.get_operation_mode()
    runtime_data = await inverter.read_runtime_data()

    print(f"Operation mode: {operation_mode.name}")
    print(f"Work mode: {runtime_data.get('work_mode_label')}")
    print(f"Battery mode: {runtime_data.get('battery_mode_label')}")
    print(f"Battery SOC: {runtime_data.get('battery_soc')}%")
    print(f"Battery power: {runtime_data.get('battery_power')}W")

    print("\n--- Test complete ---")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test.py <inverter_ip>")
        sys.exit(1)

    inverter_ip = sys.argv[1]
    asyncio.run(test_inverter(inverter_ip))
