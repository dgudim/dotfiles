#!/usr/bin/env python3
"""Publish this machine's CPU + RAM power (Intel RAPL, as measured by Netdata) to
Home Assistant over MQTT, as a single sensor announced via MQTT discovery.

All settings come from environment variables (see power-mqtt.env).
"""
import json
import os
import signal
import sys
import time
import urllib.request

import paho.mqtt.client as mqtt

NETDATA = os.environ.get("NETDATA_URL", "http://127.0.0.1:19999")
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER") or None
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD") or None
INTERVAL = int(os.environ.get("INTERVAL", "30"))
NODE = os.environ.get("NODE_ID", "microchelik")
DISCOVERY_PREFIX = os.environ.get("DISCOVERY_PREFIX", "homeassistant")

STATE_TOPIC = f"{NODE}/power/state"
AVAIL_TOPIC = f"{NODE}/power/availability"
CONFIG_TOPIC = f"{DISCOVERY_PREFIX}/sensor/{NODE}/power/config"


def netdata_avg(chart: str) -> dict:
    """Average of each dimension over the last INTERVAL seconds, e.g. {'power': 1.3}."""
    url = f"{NETDATA}/api/v1/data?chart={chart}&after=-{INTERVAL}&points=1&group=average&format=json"
    with urllib.request.urlopen(url, timeout=5) as r:
        d = json.load(r)
    if not d.get("data"):
        return {}
    return {k: v for k, v in zip(d["labels"][1:], d["data"][0][1:]) if v is not None}


def read_power():
    """CPU package + DRAM watts (on Intel, cores and iGPU are already inside the package)."""
    package = netdata_avg("cpu.powercap_intel_rapl_zone_package-0").get("power")
    if package is None:
        return None
    dram = netdata_avg("cpu.powercap_intel_rapl_subzones_package-0").get("dram", 0.0)
    return round(package + dram, 2)


DISCOVERY = {
    "name": "Power",
    "unique_id": f"{NODE}_power",
    "object_id": f"{NODE}_power",
    "state_topic": STATE_TOPIC,
    "unit_of_measurement": "W",
    "device_class": "power",
    "state_class": "measurement",
    "suggested_display_precision": 1,
    "availability_topic": AVAIL_TOPIC,
    "device": {"identifiers": [NODE], "name": NODE},
}


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{NODE}-power")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.will_set(AVAIL_TOPIC, "offline", retain=True)

    def on_connect(c, _userdata, _flags, reason_code, _props):
        if reason_code != 0:
            print(f"MQTT connect failed: {reason_code}", flush=True)
            return
        print(f"connected to {MQTT_HOST}:{MQTT_PORT}", flush=True)
        c.publish(CONFIG_TOPIC, json.dumps(DISCOVERY), retain=True)
        c.publish(AVAIL_TOPIC, "online", retain=True)

    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    def stop(*_):
        client.publish(AVAIL_TOPIC, "offline", retain=True).wait_for_publish(2)
        client.loop_stop()
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while True:
        try:
            watts = read_power()
            if watts is not None:
                client.publish(STATE_TOPIC, str(watts))
        except Exception as e:  # Netdata restarting, etc. — try again next round
            print(f"read failed: {e}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
