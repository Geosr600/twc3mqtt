from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import os
import sys
import paho.mqtt.client as mqtt

app = FastAPI()

# Configuration MQTT
MQTT_HOST = os.getenv('MQTT_HOST', None)
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', None)
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', None)

if MQTT_HOST is None:
    print("No MQTT broker specified. Please set the MQTT_HOST environment variable")
    sys.exit(1)

mqttnamespace = "mqtt/evcc/tesla/borne"

class Vitals(BaseModel):
    contactor_closed: bool
    vehicle_connected: bool
    session_s: int
    grid_v: float
    grid_hz: float
    vehicle_current_a: float
    currentA_a: float
    currentB_a: float
    currentC_a: float
    currentN_a: float
    voltageA_v: float
    voltageB_v: float
    voltageC_v: float
    relay_coil_v: float
    pcba_temp_c: float
    handle_temp_c: float
    mcu_temp_c: float
    uptime_s: int
    input_thermopile_uv: int
    prox_v: float
    pilot_high_v: float
    pilot_low_v: float
    session_energy_wh: float
    config_status: int
    evse_state: int
    current_alerts: list

state = ""

data = {
  "plugged_in": False,
  "soc": 0,
  "is_charging": 0,
  "is_dcfc": 0,
  "is_parked": 1,
  "voltage": 0,
  "current": 0,
  "kwh_charged": 0,
  "inside_temp": 20,
  "phases": 1,
  "session_start": datetime.utcnow().isoformat()
}

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "twc3evcc")
if MQTT_USERNAME is not None:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

client.connect(MQTT_HOST, MQTT_PORT)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != "Success":
        print("Unable to connect to MQTT broker")
        sys.exit(1)
    print("Connected to MQTT broker")
    client.subscribe(f"{mqttnamespace}/#")

def on_message(client, userdata, message):
    global data
    topic = message.topic
    payload = message.payload.decode("utf-8").strip()

    try:
        if topic.endswith("plugged_in"):
            data["plugged_in"] = payload.lower() == "true"
        elif topic.endswith("charging"):
            data["is_charging"] = int(payload)
        elif topic.endswith("voltage"):
            data["voltage"] = float(payload)
        elif topic.endswith("current"):
            data["current"] = float(payload)
        elif topic.endswith("energy"):
            data["kwh_charged"] = float(payload) * 1000
        elif topic.endswith("temperature"):
            data["inside_temp"] = float(payload)
        elif topic.endswith("phases"):
            data["phases"] = int(payload)
        elif topic.endswith("session_start"):
            data["session_start"] = payload
    except Exception as e:
        print("MQTT message error:", e, topic, payload)

client.on_connect = on_connect
client.on_message = on_message
client.loop_start()

@app.get("/api/1/vitals")
async def get_vitals():
    current = data["current"]
    voltage = data["voltage"]
    phases = data["phases"]
    try:
        session_time = int(datetime.utcnow().timestamp() - datetime.fromisoformat(data["session_start"]).timestamp())
    except:
        session_time = 0

    if phases > 1:
        current_b = current_c = current
        voltage_b = voltage_c = voltage
    else:
        current_b = current_c = voltage_b = voltage_c = 0

    vitals = Vitals(
        contactor_closed=bool(data["is_charging"]),
        vehicle_connected=bool(data["plugged_in"]),
        session_s=session_time,
        grid_v=voltage,
        grid_hz=50.0,
        vehicle_current_a=current,
        currentA_a=current,
        currentB_a=current_b,
        currentC_a=current_c,
        currentN_a=0.0,
        voltageA_v=voltage,
        voltageB_v=voltage_b,
        voltageC_v=voltage_c,
        relay_coil_v=11.9,
        pcba_temp_c=7.4,
        handle_temp_c=1.8,
        mcu_temp_c=data["inside_temp"],
        uptime_s=3600,
        input_thermopile_uv=-176,
        prox_v=0.0,
        pilot_high_v=11.9,
        pilot_low_v=11.8,
        session_energy_wh=data["kwh_charged"],
        config_status=5,
        evse_state=1,
        current_alerts=[]
    )
    return vitals
