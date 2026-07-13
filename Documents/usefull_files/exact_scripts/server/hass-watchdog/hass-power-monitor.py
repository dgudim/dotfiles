import os
import sys
import time
import json
import requests

CONFIG_PATH = "hass-power-monitor-config.json"

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

def get_sensor_state(url, api_key, sensor_id):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }
    try:
        response = requests.get(f"{url}/api/states/{sensor_id}", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        state = data.get("state")
        return state
    except Exception as e:
        print(f"Error fetching sensor state: {e}", file=sys.stderr)
        return None

def main():
    config = load_config()

    ha_url = config["ha_url"]
    api_key = config["api_key"]
    sensor_id = config["sensor_id"]
    delay_seconds = config["shutdown_delay_minutes"] * 60

    outage_start_time = None
    print("UPS Monitor Service Started.")

    while True:
        state = get_sensor_state(ha_url, api_key, sensor_id)

        if state in ["off", "false", False]:
            if outage_start_time is None:
                outage_start_time = time.time()
                print("Power outage detected!")

            elapsed_time = time.time() - outage_start_time
            print(f"Remaining time until shutdown: {int(max(0, int(delay_seconds - elapsed_time)) / 60)} minutes.")

            if elapsed_time >= delay_seconds:
                print("Power outage exceeded threshold. Shutting down.")
                os.system("shutdown -h now")
                sys.exit(0)
        else:
            if outage_start_time is not None:
                print("Power restored.")
                outage_start_time = None

        time.sleep(30)

if __name__ == "__main__":
    main()
