from dotenv import load_dotenv
import os
import requests
import paramiko
import json
import psutil
import subprocess
import re
import time
import paho.mqtt.client as mqtt
import ssl
import threading
from datetime import datetime

load_dotenv()

BAMBU_IP = os.environ.get("printer_IP")        # your printer's LAN IP
BAMBU_ACCESS_CODE = os.environ.get("printer_ACCESS_CODE")  # from Settings > Network > Access Code
BAMBU_SERIAL = os.environ.get("printer_SERIAL")

FINISH_DISPLAY_SECONDS = 60

_printer_status = {
    "gcode_state": "Unknown",
    "progress": None,
    "layer": None,
    "total_layers": None,
    "nozzle_temp": None,
    "bed_temp": None,
    "remaining_min": None,
}

STATUS_LABELS = {
    "RUNNING": "Printing",
    "PAUSE": "Paused",
    "FINISH": "Finished",
    "IDLE": "Idle",
}

_printer_lock = threading.Lock()
_finish_transition_time = None

def get_weather(lat=os.environ.get("latitude"), lon=os.environ.get("longitude")): #coordinates of your address 
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,precipitation_probability,weather_code"
        f"&daily=sunrise,sunset"
        f"&temperature_unit=fahrenheit"
        f"&timezone=auto"
    )
    try:
        response = requests.get(url, timeout=5)
        payload = response.json()
        current = payload["current"]
        daily = payload["daily"]

        # timezone=auto returns local ISO8601 strings, e.g. "2026-09-20T06:45"
        sunrise = datetime.fromisoformat(daily["sunrise"][0])
        sunset = datetime.fromisoformat(daily["sunset"][0])
        now = datetime.now()
        is_night = now < sunrise or now > sunset

        return {
            "temp": round(current["temperature_2m"]),
            "precip_chance": current.get("precipitation_probability", 0),
            "weather_code": current["weather_code"],
            "is_night": is_night,
        }
    except Exception as e:
        print(f"Weather fetch failed: {e}")
        return {"temp": None, "precip_chance": None, "weather_code": None, "is_night": False}

WEATHER_ICON_MAP_DAY = {
    "clear":  "\uf00d",  # wi-day-sunny
    "cloudy": "\uf002",  # wi-day-cloudy
    "fog":    "\uf003",  # wi-day-fog
    "rain":   "\uf008",  # wi-day-rain
    "snow":   "\uf00a",  # wi-day-snow
    "storm":  "\uf005",  # wi-day-lightning
}

WEATHER_ICON_MAP_NIGHT = {
    "clear":  "\uf02e",  # wi-night-clear
    "cloudy": "\uf086",  # wi-night-alt-cloudy
    "fog":    "\uf04a",  # wi-night-fog
    "rain":   "\uf036",  # wi-night-alt-rain
    "snow":   "\uf02a",  # wi-night-alt-snow
    "storm":  "\uf02d",  # wi-night-alt-thunderstorm
}

def get_weather_icon_category(code):
    if code is None:
        return "unknown"
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloudy"

def _on_connect(client, userdata, flags, rc):
    client.subscribe(f"device/{BAMBU_SERIAL}/report")

def _on_message(client, userdata, msg):
    global _finish_transition_time
    try:
        payload = json.loads(msg.payload.decode())
        p = payload.get("print", {})
        if p:
            with _printer_lock:
                new_state = p.get("gcode_state", _printer_status["gcode_state"])
                old_state = _printer_status["gcode_state"]

                if new_state == "FINISH" and old_state != "FINISH":
                    _finish_transition_time = time.time()
                elif new_state != "FINISH":
                    _finish_transition_time = None

                _printer_status["gcode_state"] = new_state
                _printer_status["progress"] = p.get("mc_percent", _printer_status["progress"])
                _printer_status["layer"] = p.get("layer_num", _printer_status["layer"])
                _printer_status["total_layers"] = p.get("total_layer_num", _printer_status["total_layers"])
                _printer_status["nozzle_temp"] = p.get("nozzle_temper", _printer_status["nozzle_temp"])
                _printer_status["bed_temp"] = p.get("bed_temper", _printer_status["bed_temp"])
                _printer_status["remaining_min"] = p.get("mc_remaining_time", _printer_status["remaining_min"])
    except Exception as e:
        print(f"Bambu MQTT message parse failed: {e}")

def start_bambu_listener():
    client = mqtt.Client()
    client.username_pw_set("bblp", BAMBU_ACCESS_CODE)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_connect = _on_connect
    client.on_message = _on_message

    def run():
        while True:
            try:
                client.connect(BAMBU_IP, 8883, keepalive=30)
                client.loop_forever()
            except Exception as e:
                print(f"Bambu MQTT connection failed, retrying in 10s: {e}")
                time.sleep(10)

    threading.Thread(target=run, daemon=True).start()

def get_printer_status():
    with _printer_lock:
        status = dict(_printer_status)

    if status["gcode_state"] == "FINISH" and _finish_transition_time is not None:
        elapsed = time.time() - _finish_transition_time
        status["display_state"] = "IDLE" if elapsed > FINISH_DISPLAY_SECONDS else "FINISH"
    else:
        status["display_state"] = status["gcode_state"]

    return status
def parse_numeric(value_str):
    """LibreHardwareMonitor returns values like '45.2 %' or '67.0 °C' — strip units."""
    if value_str is None:
        return None
    try:
        # Grab the leading numeric portion, ignore whatever unit follows
        match = re.search(r"[-+]?\d*\.?\d+", value_str)
        return float(match.group()) if match else None
    except (TypeError, ValueError):
        return None

def get_pc_temps(host=os.environ.get("desktop_name")):
    url = f"http://{host}:8085/data.json"

    try:
        response = requests.get(url, timeout=3)
        payload = response.json()

        cpu_temp = None
        gpu_temp = None

        # Helper to recursively look for Temperature nodes in the JSON tree
        def find_temps(node):
            nonlocal cpu_temp, gpu_temp

            # Identify CPU and GPU by text labels
            if "Text" in node:
                # Common labels: "Intel Core...", "AMD Ryzen...", "NVIDIA GeForce...", "AMD Radeon..."
                # Look specifically for the "Temperatures" sub-sections
                if "CPU" in node["Text"] or "Intel" in node["Text"] or "AMD" in node["Text"]:
                    for child in node.get("Children", []):
                        if child.get("Text") == "Temperatures":
                            # Pull the core or package temperature
                            for sensor in child.get("Children", []):
                                if "Core" in sensor.get("Text") or "Package" in sensor.get("Text"):
                                    cpu_temp = sensor.get("Value")

                if "NVIDIA" in node["Text"] or "GPU" in node["Text"] or "Radeon" in node["Text"]:
                    for child in node.get("Children", []):
                        if child.get("Text") == "Temperatures":
                            for sensor in child.get("Children", []):
                                if "Core" in sensor.get("Text"):
                                    gpu_temp = sensor.get("Value")

            for child in node.get("Children", []):
                find_temps(child)

        find_temps(payload)
        return cpu_temp, gpu_temp

    except requests.exceptions.RequestException:
        # Returns offline status if PC is off or disconnected
        return "Offline", "Offline"

def get_desktop_stats(host=os.environ.get("desktop_name")):
    url = f"http://{host}:8085/data.json"
    try:
        response = requests.get(url, timeout=3)
        payload = response.json()

        stats = {"cpu_temp": None, "gpu_temp": None, "cpu_load": None, "gpu_load": None, "mem_used_pct": None}

        def walk(node):
            text = node.get("Text", "")

            if "CPU" in text or "Intel" in text or "AMD" in text and "Radeon" not in text:
                for child in node.get("Children", []):
                    if child.get("Text") == "Temperatures":
                        for s in child.get("Children", []):
                            if "Package" in s.get("Text", "") or "Core" in s.get("Text", ""):
                                stats["cpu_temp"] = parse_numeric(s.get("Value"))
                    if child.get("Text") == "Load":
                        for s in child.get("Children", []):
                            if "CPU Total" in s.get("Text", ""):
                                stats["cpu_load"] = parse_numeric(s.get("Value"))

            if "NVIDIA" in text or "Radeon" in text:
                for child in node.get("Children", []):
                    if child.get("Text") == "Temperatures":
                        for s in child.get("Children", []):
                            if "Core" in s.get("Text", ""):
                                stats["gpu_temp"] = parse_numeric(s.get("Value"))
                    if child.get("Text") == "Load":
                        for s in child.get("Children", []):
                            if "Core" in s.get("Text", "") or "GPU Core" in s.get("Text", ""):
                                stats["gpu_load"] = parse_numeric(s.get("Value"))

            if text == "Total Memory":
                for child in node.get("Children", []):
                    if child.get("Text") == "Load":
                        for s in child.get("Children", []):
                            if "Memory" in s.get("Text", ""):
                                stats["mem_used_pct"] = parse_numeric(s.get("Value"))

            for child in node.get("Children", []):
                walk(child)

        walk(payload)
        return stats

    except requests.exceptions.RequestException:
        return {"cpu_temp": "N/A", "gpu_temp": "N/A", "cpu_load": "N/A", "gpu_load": "N/A", "mem_used_pct": "N/A"}

def get_server_temps(host, user):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, timeout=5)

        stdin, stdout, stderr = client.exec_command("sensors -j")
        output = stdout.read().decode()
        client.close()

        sensor_data = json.loads(output)

        return {
            "cpu": round(sensor_data["coretemp-isa-0000"]["Package id 0"]["temp1_input"], 1),
        }

    except Exception as e:
        print(f"Server temp fetch failed: {e}")
        return {"cpu": "N/A", "nvme": "N/A"}

def get_server_stats(host, user):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, timeout=5)

        # CPU% via /proc/stat sampling isn't a one-liner over SSH, so use `top` in batch mode instead
        cmd = (
            "top -bn2 -d 1 | grep 'Cpu(s)' | tail -1 && "
            "free -m | awk '/Mem:/ {printf \"%.1f\", $3/$2 * 100}' && "
            "echo && sensors -j && echo '---DOCKER---' && "
            'docker ps -a --format "{{.Names}}|{{.Status}}"'
        )
        stdin, stdout, stderr = client.exec_command(cmd)
        output = stdout.read().decode()
        client.close()

        sections = output.split("---DOCKER---")
        top_and_sensors = sections[0].splitlines()
        docker_output = sections[1].strip() if len(sections) > 1 else ""

        cpu_line = top_and_sensors[0]  # e.g. "%Cpu(s):  5.9 us,  2.0 sy,  0.0 ni, 91.7 id, ..."
        # Total (non-idle) CPU usage = 100 - idle%, rather than just the 'us' (user) field,
        # so this is comparable to psutil.cpu_percent() on the Pi.
        idle_match = re.search(r"([\d.]+)\s*id", cpu_line)
        cpu_load = round(100 - float(idle_match.group(1)), 1) if idle_match else None

        mem_used_pct = float(top_and_sensors[1])

        sensor_json = "\n".join(top_and_sensors[2:])
        sensor_data = json.loads(sensor_json)
        cpu_temp = sensor_data["coretemp-isa-0000"]["Package id 0"]["temp1_input"]

        containers = []
        for line in docker_output.splitlines():
            if "|" in line:
                name, status = line.split("|", 1)
                containers.append({"name": name, "status": status, "up": status.startswith("Up")})

        return {
            "cpu_temp": round(cpu_temp, 1),
            "cpu_load": cpu_load,
            "mem_used_pct": round(mem_used_pct, 1),
            "containers": containers,
        }

    except Exception as e:
        print(f"Server stats fetch failed: {e}")
        return {"cpu_temp": "N/A", "cpu_load": "N/A", "mem_used_pct": "N/A", "containers": []}

def get_pi_temp():
    try:
        output = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        match = re.search(r"temp=([\d.]+)", output)
        return round(float(match.group(1)), 1) if match else None
    except Exception as e:
        print(f"Pi temp fetch failed: {e}")
        return "N/A"

def get_pi_stats():
    return {
        "cpu_load": psutil.cpu_percent(interval=1.5),
        "mem_used_pct": psutil.virtual_memory().percent,
    }
def get_pi_docker_status():
    try:
        output = subprocess.check_output(
            ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"],
            timeout=5
        ).decode()

        containers = []
        for line in output.strip().splitlines():
            if "|" in line:
                name, status = line.split("|", 1)
                containers.append({"name": name, "status": status, "up": status.startswith("Up")})
        return containers

    except Exception as e:
        print(f"Pi Docker status fetch failed: {e}")
        return []

def truncate_name(name, max_length=20):
    if len(name) > max_length:
        return name[:max_length] + "..."
    return name

def draw_text_right_aligned(draw, right_x, y, text, font, fill=0):
    text_width = draw.textlength(text, font=font)
    x = right_x - text_width
    draw.text((x, y), text, font=font, fill=fill)

def get_stats():
    desktop = get_desktop_stats()
    pi = get_pi_stats()
    server = get_server_stats(os.environ.get("server_name"), os.environ.get("server_username"))
    pi_temp = get_pi_temp()
    printer = get_printer_status()
    weather = get_weather()
    pi_docker = get_pi_docker_status()

    return {
        "time": datetime.now().strftime("%I:%M %p").lstrip("0"),
        "desktop": desktop,
        "pi": {**pi, "cpu_temp": pi_temp},
        "server": server,
        "printer": printer,
        "weather": weather,
        "pi_docker": pi_docker,
    }
