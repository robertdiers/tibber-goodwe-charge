# tibber-goodwe-charge

charge battery connected to a Goodwe inverter based on tibber API prices.

While the price is cheap and we are inside the configured month/hour window the inverter
stays in `ECO_CHARGE`: it charges from the grid up to `target_soc` and then keeps the
battery from discharging, so the house is supplied from the grid while the battery is
saved for the expensive hours. As soon as the price rises above `price_stop` or the time
window ends, the script switches back to `GENERAL` and the battery supplies the house.
`price_start` and `price_stop` form a hysteresis: enter at `price_start`, leave at
`price_stop`.

### Supported inverter families

| Family | `ECO_CHARGE` switching | `TARGET_SOC` enforced by inverter |
|---|---|---|
| ES / EM / BP | yes | only with EcoMode V2 |
| ET / EH / BT / BH | yes | only with EcoMode V2 |
| DT / MS / NS / XS | **no** | not supported |

`TARGET_SOC` is only stored and enforced by the inverter on EcoMode V2 firmware:

- **ES/EM/BP**: ESU/ESA with DSP1 >= 22, EMU/EMJ with DSP1 >= 11, BPS/BPU with DSP1 >= 10
- **ET/EH/BT/BH**: ETU firmware >= 19

With EcoMode V1 the library accepts `eco_mode_soc` but silently ignores it, so the inverter
charges up to the BMS limit (usually 100 %). The script detects this at runtime, shows
`target SOC: no (EcoMode V1, charges to BMS limit)` in `test.py`, and logs a warning when it
starts grid charging while `TARGET_SOC < 1.0`. The hold behaviour (battery does not discharge
during the cheap period) still applies.

The DT/MS/NS/XS families do not implement `get_operation_mode()` / `set_operation_mode()` in
the `goodwe` library. The script detects that `ECO_CHARGE` is missing, logs a clear message and
does **not** write any mode change to the inverter.

The ES family (e.g. **GW5048D-ES**) uses the inverter's Eco mode: the script switches between
`GENERAL` (normal self consumption) and `ECO_CHARGE` (grid charging up to `TARGET_SOC`).

### Defaults

please check config in tibber-goodwe-charge.ini file, could be overridden by Docker env variables

### Tibber API

How to get PAT? (personal access token)

Login at https://developer.tibber.com and you get one.

How to get the Home ID?

```
curl -H "Authorization: Bearer YOUR_PAT" \
     -H "Content-Type: application/json" \
     -X POST \
     -d '{ "query": "{ viewer { homes { id appNickname address { address1 } } } }" }' \
     https://api.tibber.com/v1-beta/gql
```

### Docker usage

Environment variables (all can be overridden):

| Variable | Description | Example |
|----------|-------------|---------|
| HOME_ID | Tibber home ID | abc123 |
| PAT | Tibber Personal Access Token | xxxx |
| INVERTER_IP | Goodwe inverter IP | 192.168.1.186 |
| INVERTER_FAMILY | Force inverter family (optional, default: auto detect) | ES |
| TARGET_SOC | Target SOC for grid charging (0.0-1.0) | 0.50 |
| PRICE_START | Max price (EUR/kWh) to START charging | 0.23 |
| PRICE_STOP | Price (EUR/kWh) to STOP charging | 0.26 |
| MONTHS | Months allowed for charging (comma-separated) | 10,11,12,01,02,03 |
| START_HOUR | Start hour for charging window | 1 |
| STOP_HOUR | Stop hour for charging window | 4 |
| CHARGE_POWER | Charge power in % of inverter rating | 100 |

Example:
```
docker run -d --restart always \
  -e HOME_ID=abc123 \
  -e PAT=xxxx \
  -e INVERTER_IP=192.168.1.186 \
  -e TARGET_SOC=0.5 \
  -e PRICE_START=0.23 \
  -e PRICE_STOP=0.26 \
  -e MONTHS=10,11,12,01,02,03 \
  -e START_HOUR=1 \
  -e STOP_HOUR=4 \
  --name tibbergoodwecharge ghcr.io/robertdiers/tibber-goodwe-charge:RELEASE
```

### ES family notes (e.g. GW5048D-ES)

- The inverter is detected automatically from its serial number. If detection fails, set
  `family=ES` in the config or `INVERTER_FAMILY=ES`.
- `ECO_CHARGE` writes an all-day charge schedule into the inverter (Eco mode group 1).
  With EcoMode V2 firmware (ARM >= 14, DSP1 >= 22 on ES) the target SOC is written as well,
  so the inverter stops charging by itself at `target_soc` but stays in eco charge mode.
  During that time the battery does not discharge while the grid is available, so the
  house is supplied from the grid until the price rises or the window ends. With older
  EcoMode V1 firmware the target SOC is ignored (charges to the BMS limit) and the script
  logs a warning; the hold behaviour until the price/time boundary is unchanged.
- `target_soc=0.50` means grid charging stops at 50 %. If the battery is already above
  the target (e.g. from PV), eco charge mode still prevents discharge and the grid covers
  the load during the cheap period.
- `CHARGE_POWER=100` means full rated power (GW5048D-ES: about 4.6 kW / 100 A).
  Limit it if the battery or BMS cannot handle that.
- Grid charging must be allowed by local regulations.
- If the battery does not carry load after switching back to `GENERAL`, check the DOD
  (depth of discharge) setting of the inverter.
- The GoodWe dongle usually listens on **UDP** port 8899, not TCP. The script therefore
  checks availability by an actual protocol connection instead of a TCP port check.
- The cron wrapper waits a random 0–10 seconds before each poll. This reduces collisions
  when other local tools (e.g. Home Assistant) read the same dongle.

### Testing an inverter

Read-only (safe):
```
cd python
python3 test.py 192.168.1.108
```

Short real charge test (switches to ECO_CHARGE and always back to GENERAL):
```
cd python
python3 test.py 192.168.1.108 --write --power 20 --soc 65 --hold 60
```

End-to-end test of the real decision flow with a simulated Tibber price
(cheap price -> ECO_CHARGE, cheap again -> stay ECO_CHARGE, then expensive price -> GENERAL):
```
cd python
python3 test.py 192.168.1.108 --e2e --power 20 --soc 65 --hold 60
```

With `--soc` below the current SOC you can verify the hold behaviour: the inverter stays in
`ECO_CHARGE` with 0 W battery power while the grid supplies the house.
