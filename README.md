# tibber-goodwe-charge

charge battery connected to Goodwe inverter (ET/BT/EH, no ES) based on tibber API prices up to a defined soc limit

### Defaults

plaese check config in tibber-goodwe-charge.ini file, could be overridden by Docker env variables

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
| BATTERY_SOC_START | SOC threshold to START charging (0.0-1.0) | 0.30 |
| BATTERY_SOC_STOP | SOC threshold to STOP charging (0.0-1.0) | 0.60 |
| PRICE_START | Max price (EUR/kWh) to START charging | 0.23 |
| PRICE_STOP | Price (EUR/kWh) to STOP charging | 0.26 |
| MONTHS | Months allowed for charging (comma-separated) | 10,11,12,01,02,03 |
| START_HOUR | Start hour for charging window | 1 |
| STOP_HOUR | Stop hour for charging window | 4 |

Example:
```
docker run -d --restart always \
  -e HOME_ID=abc123 \
  -e PAT=xxxx \
  -e INVERTER_IP=192.168.1.186 \
  -e BATTERY_SOC_START=0.3
  -e BATTERY_SOC_STOP=0.6
  -e PRICE_START=0.23 \
  -e PRICE_STOP=0.26 \
  -e MONTHS=10,11,12,01,02,03 \
  --name tibbergoodwecharge ghcr.io/robertdiers/tibber-goodwe-charge:1.1.0
```
