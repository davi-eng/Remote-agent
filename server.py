from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

TOKEN = "mysecrettoken123"
home_data = {}
command_queue = []
results = []

def auth(req):
    return req.headers.get("Authorization") == f"Bearer {TOKEN}"

@app.route("/register", methods=["POST"])
def register():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    global home_data
    home_data = request.get_json()
    print(f"[HOME PHONE CONNECTED] {home_data}")
    return jsonify({"status": "registered"})

@app.route("/poll", methods=["GET"])
def poll():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    if command_queue:
        cmd = command_queue.pop(0)
        return jsonify({"command": cmd})
    return jsonify({"command": None})

@app.route("/result", methods=["POST"])
def result():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    results.append(data)
    print(f"[RESULT] {data}")
    return jsonify({"status": "received"})

@app.route("/results", methods=["GET"])
def get_results():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(results)

@app.route("/send", methods=["POST"])
def send():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    cmd = request.get_json().get("command")
    command_queue.append(cmd)
    print(f"[QUEUED] {cmd}")
    return jsonify({"status": "queued"})

@app.route("/status", methods=["GET"])
def status():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(home_data)

@app.route("/start-mirror", methods=["POST"])
def start_mirror():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    command_queue.append("adb tcpip 5555")
    command_queue.append(
        "nohup ngrok tcp 5555 "
        "--log=/sdcard/ngrok.log "
        "--log-format=json &"
    )
    return jsonify({"status": "mirror commands queued"})

@app.route("/mirror-address", methods=["POST"])
def mirror_address():
    if not auth(request):
        return jsonify({"error": "Unauthorized"}), 401
    command_queue.append("cat /sdcard/ngrok.log")
    return jsonify({"status": "queued — check /results"})

if __name__ == "__main__":
    print("[SERVER] Running on port 5000")
    print("[INFO] Start ngrok separately with:")
    print("       ngrok http 5000")
    app.run(host="0.0.0.0", port=5000)
