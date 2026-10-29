import time
import requests
import random
from datetime import datetime


# ============================================================
# EcoTwin-AI Digital Twin Presentation Simulator
# Ambient temperature = REAL (ESP32 + DHT22), falls back to demo
# All other values    = SIMULATED
# ============================================================

BASE_URL = "http://127.0.0.1:5000"
PREDICT_URL = f"{BASE_URL}/api/predict"
TELEMETRY_URL = f"{BASE_URL}/api/telemetry/"
ESP32_URL = f"{BASE_URL}/api/telemetry/esp32"
SYNC_URL = f"{BASE_URL}/api/digital-twin/synchronize"

FACILITY_ID = 1

INTERVAL_SECONDS = 3

# ESP32 readings older than this are treated as stale
ESP32_MAX_AGE_SECONDS = 30


# ============================================================
# SIMULATION SCENARIOS
# ============================================================

SCENARIOS = [

    {
        "name": "NORMAL OPERATION",
        "description":
            "Solar energy asset operating under normal conditions.",
        "ambient_temperature": 30.0,
        "module_temperature": 40.0,
        "voltage": 20.5,
        "current": 1.05,
        "irradiance": 950.0,
        "vibration": 0.8,
    },

    {
        "name": "TEMPERATURE RISE",
        "description":
            "Module temperature is increasing and output is beginning to decline.",
        "ambient_temperature": 34.0,
        "module_temperature": 58.0,
        "voltage": 19.8,
        "current": 0.90,
        "irradiance": 920.0,
        "vibration": 1.5,
    },

    {
        "name": "WARNING CONDITION",
        "description":
            "Abnormal temperature and vibration conditions are detected.",
        "ambient_temperature": 38.0,
        "module_temperature": 72.0,
        "voltage": 18.8,
        "current": 0.70,
        "irradiance": 880.0,
        "vibration": 2.8,
    },

    {
        "name": "HIGH RISK CONDITION",
        "description":
            "Severe thermal stress, reduced electrical output and increased vibration.",
        "ambient_temperature": 43.0,
        "module_temperature": 88.0,
        "voltage": 17.2,
        "current": 0.45,
        "irradiance": 820.0,
        "vibration": 4.5,
    },

    {
        "name": "RECOVERY",
        "description":
            "Operating conditions are returning toward normal.",
        "ambient_temperature": 32.0,
        "module_temperature": 45.0,
        "voltage": 20.0,
        "current": 1.00,
        "irradiance": 970.0,
        "vibration": 0.9,
    },
]


# ============================================================
# READ REAL TEMPERATURE FROM ESP32 (via Flask)
# ============================================================

def get_esp32_temperature():
    """Return the ESP32's latest real ambient temperature,
    or None if unavailable or stale."""

    try:
        response = requests.get(ESP32_URL, timeout=3)
        esp32 = response.json().get("esp32", {})

        temperature = esp32.get("ambient_temperature")
        timestamp = esp32.get("timestamp")

        if temperature is None or timestamp is None:
            return None

        age = (
            datetime.utcnow()
            - datetime.fromisoformat(timestamp)
        ).total_seconds()

        if age > ESP32_MAX_AGE_SECONDS:
            return None

        return round(float(temperature), 2)

    except Exception:
        return None


# ============================================================
# DISPLAY HEADER
# ============================================================

def show_header():

    print()
    print("=" * 72)
    print("                         ECOTWIN-AI")
    print("              DIGITAL TWIN DEMO SIMULATOR")
    print("=" * 72)

    print()
    print("Physical Solar Energy Asset")
    print("            ↓")
    print("       ESP32 / Sensors")
    print("            ↓")
    print("      Live Telemetry")
    print("            ↓")
    print("       Digital Twin")
    print("            ↓")
    print("       TinyML Model")
    print("            ↓")
    print("      Explainable AI")
    print("            ↓")
    print(" Maintenance Recommendation")
    print()

    print("=" * 72)
    print()


# ============================================================
# TEST BACKEND
# ============================================================

def test_backend():

    print()
    print("Testing EcoTwin-AI telemetry API...")
    print()

    test_data = {
        "facility_id": FACILITY_ID,
        "ambient_temperature": 30.0,
        "module_temperature": 40.0,
        "voltage": 20.5,
        "current": 1.0,
        "power": 20.5,
        "irradiance": 950.0,
        "vibration": 0.8
    }

    try:

        response = requests.post(
            TELEMETRY_URL,
            json=test_data,
            timeout=5
        )

        print(f"Telemetry API response: {response.status_code}")

        if response.status_code == 200:

            print()
            print("Backend connection: CONNECTED")
            print("Telemetry API: WORKING")
            print("Test telemetry: ACCEPTED")
            print()

            esp32_temp = get_esp32_temperature()

            if esp32_temp is not None:
                print(f"ESP32 sensor: ONLINE ({esp32_temp} °C)")
            else:
                print(
                    "ESP32 sensor: NOT DETECTED "
                    "(demo temperature will be used)"
                )

            print()
            return True

        print()
        print("Flask server was reached.")
        print("However, the telemetry request was rejected.")
        print()
        print("HTTP Status:")
        print(response.status_code)
        print()
        print("Server Response:")
        print(response.text)
        print()

        return False

    except requests.exceptions.ConnectionError:

        print()
        print("Backend connection: FAILED")
        print()
        print("Could not connect to Flask at:")
        print(BASE_URL)
        print()
        print("Start Flask using:")
        print("python -m backend.app")
        print()

        return False

    except requests.exceptions.Timeout:

        print()
        print("Backend connection: TIMEOUT")
        print()
        print("Flask did not respond within 5 seconds.")
        print()

        return False

    except requests.exceptions.RequestException as error:

        print()
        print("Backend request error:")
        print(error)
        print()

        return False

    except Exception as error:

        print()
        print("Unexpected error:")
        print(error)
        print()

        return False


# ============================================================
# GENERATE TELEMETRY
# Returns (data, source) where source is "ESP32" or "DEMO"
# ============================================================

def generate_telemetry(scenario):

    real_temperature = get_esp32_temperature()

    if real_temperature is not None:
        ambient_temperature = real_temperature
        source = "ESP32"
    else:
        # ESP32 offline or stale: fall back to the demo value
        ambient_temperature = round(
            scenario["ambient_temperature"]
            + random.uniform(-0.5, 0.5),
            2
        )
        source = "DEMO"

    module_temperature = round(
        scenario["module_temperature"]
        + random.uniform(-1.5, 1.5),
        2
    )

    voltage = round(
        scenario["voltage"]
        + random.uniform(-0.15, 0.15),
        2
    )

    current = round(
        scenario["current"]
        + random.uniform(-0.05, 0.05),
        2
    )

    current = max(current, 0.05)

    irradiance = round(
        scenario["irradiance"]
        + random.uniform(-20, 20),
        2
    )

    irradiance = max(irradiance, 0)

    vibration = round(
        scenario["vibration"]
        + random.uniform(-0.2, 0.2),
        2
    )

    vibration = max(vibration, 0)

    power = round(voltage * current, 2)

    data = {
        "facility_id": FACILITY_ID,
        "ambient_temperature": ambient_temperature,
        "module_temperature": module_temperature,
        "voltage": voltage,
        "current": current,
        "power": power,
        "irradiance": irradiance,
        "vibration": vibration
    }

    return data, source


# ============================================================
# SEND TELEMETRY TO FLASK
# ============================================================

def send_telemetry(data):

    try:

        response = requests.post(
            TELEMETRY_URL,
            json=data,
            timeout=5
        )

        if response.status_code == 200:
            return True, response.json()

        return False, response.text

    except requests.exceptions.RequestException as error:

        return False, str(error)


# ============================================================
# SYNCHRONIZE DIGITAL TWIN
# ============================================================

def synchronize_twin():

    try:
        requests.post(
            SYNC_URL,
            json={"facility_id": FACILITY_ID},
            timeout=8
        )
    except requests.exceptions.RequestException:
        pass


# ============================================================
# DISPLAY SCENARIO
# ============================================================

def display_scenario(scenario):

    print()
    print()
    print("#" * 72)
    print(f"SCENARIO: {scenario['name']}")
    print("#" * 72)
    print()
    print(scenario["description"])
    print()

    print("Scenario conditions (ambient uses the ESP32 when online):")
    print("-" * 72)

    print(
        f"Ambient Temperature : "
        f"{scenario['ambient_temperature']:.1f} °C (demo fallback)"
    )
    print(
        f"Module Temperature  : "
        f"{scenario['module_temperature']:.1f} °C"
    )
    print(f"Voltage             : {scenario['voltage']:.2f} V")
    print(f"Current             : {scenario['current']:.2f} A")

    power = scenario["voltage"] * scenario["current"]

    print(f"Power               : {power:.2f} W")
    print(f"Irradiance          : {scenario['irradiance']:.0f} W/m²")
    print(f"Vibration           : {scenario['vibration']:.2f} mm/s")
    print()


# ============================================================
# RUN ONE SCENARIO
# ============================================================
def run_prediction(data):
    """Run the ML model + XAI on the current reading."""
    try:
        payload = dict(data)
        payload["device_id"] = "SOLAR-ESP32-001"
        requests.post(PREDICT_URL, json=payload, timeout=8)
    except requests.exceptions.RequestException:
        pass

def run_scenario(scenario):

    display_scenario(scenario)

    # Six readings per scenario (~18 seconds at 3 seconds each)

    for reading_number in range(1, 7):

        data, source = generate_telemetry(scenario)

        success, result = send_telemetry(data)

        if success:

            run_prediction(data)
            synchronize_twin()

            print(
                f"[LIVE {reading_number}/6] "
                f"T={data['ambient_temperature']}°C ({source}) | "
                f"Module={data['module_temperature']}°C | "
                f"V={data['voltage']}V | "
                f"I={data['current']}A | "
                f"P={data['power']}W | "
                f"Irr={data['irradiance']}W/m² | "
                f"Vib={data['vibration']}mm/s"
            )

        else:

            print()
            print("[TELEMETRY ERROR]")
            print(result)
            print()

        time.sleep(INTERVAL_SECONDS)


# ============================================================
# MAIN SIMULATION
# ============================================================

def main():

    show_header()

    print("Facility ID:", FACILITY_ID)
    print("Telemetry endpoint:")
    print(TELEMETRY_URL)
    print("ESP32 endpoint:")
    print(ESP32_URL)
    print()

    if not test_backend():

        print()
        print("=" * 72)
        print("SIMULATION STOPPED")
        print("=" * 72)
        print()

        return

    print()
    print("Starting presentation simulation in 3 seconds...")

    time.sleep(3)

    print()
    print("Dashboard:")
    print("http://127.0.0.1:5000/dashboard")
    print()
    print("Live telemetry transmission started.")
    print("Press CTRL+C to stop.")
    print()

    try:

        while True:

            for scenario in SCENARIOS:

                run_scenario(scenario)

                print()
                print(f"Completed scenario: {scenario['name']}")
                print("Updating Digital Twin...")

                time.sleep(3)

            print()
            print("=" * 72)
            print("       SIMULATION CYCLE COMPLETED")
            print("=" * 72)
            print()
            print("Restarting from normal operation...")
            print()

            time.sleep(5)

    except KeyboardInterrupt:

        print()
        print()
        print("=" * 72)
        print("        ECOTWIN-AI SIMULATION STOPPED")
        print("=" * 72)
        print()


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()