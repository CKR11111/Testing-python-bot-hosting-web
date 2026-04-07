from flask import Flask, request, render_template, redirect, url_for, jsonify
import os, subprocess, zipfile, shutil, pathlib, time, threading, json, uuid, signal, sys

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BOT_ROOT = os.path.join(BASE_DIR, "bots")
META_FILE = os.path.join(BOT_ROOT, "_meta.json")
os.makedirs(BOT_ROOT, exist_ok=True)

running_processes = {} 

def load_meta():
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_meta(d):
    with open(META_FILE, "w") as f: json.dump(d, f)

meta = load_meta()

def is_running(bid):
    if bid in running_processes:
        if running_processes[bid].poll() is None: return True
    return False

@app.route("/api/status")
def api_status():
    out = []
    for bid, info in meta.items():
        out.append({"id": bid, "name": info.get("name"), "running": is_running(bid)})
    return jsonify(out)

@app.route("/")
def index():
    return render_template("index.html", bots=meta)

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("zipfile")
    if not f or not f.filename.lower().endswith(".zip"): return "Invalid Zip", 400
    bid = "inst_" + uuid.uuid4().hex[:6]
    folder = os.path.join(BOT_ROOT, bid)
    os.makedirs(folder, exist_ok=True)
    zip_path = os.path.join(BOT_ROOT, f"{bid}.zip")
    f.save(zip_path)
    with zipfile.ZipFile(zip_path, "r") as z: z.extractall(folder)
    os.remove(zip_path)
    meta[bid] = {"name": pathlib.Path(f.filename).stem}
    save_meta(meta)
    return redirect(url_for("index"))

@app.route("/start/<bot>")
def start(bot):
    if bot not in meta: return "404", 404
    if is_running(bot): stop(bot)
    folder = os.path.join(BOT_ROOT, bot)
    log_file = open(os.path.join(folder, "run.log"), "a")
    
    # Render ma bot chalauna chahine libraries auto-install garchha
    subprocess.run([sys.executable, "-m", "pip", "install", "pycryptodome", "protobuf", "protobuf-decoder", "requests"], cwd=folder)
    
    # Direct Process Execution
    proc = subprocess.Popen([sys.executable, "ckr.py"], cwd=folder, stdout=log_file, stderr=log_file, start_new_session=True)
    running_processes[bot] = proc
    return redirect(url_for("index"))

@app.route("/stop/<bot>")
def stop(bot):
    if bot in running_processes:
        try: os.killpg(os.getpgid(running_processes[bot].pid), signal.SIGTERM)
        except: running_processes[bot].terminate()
        del running_processes[bot]
    return redirect(url_for("index"))

@app.route("/delete/<bot>")
def delete(bot):
    stop(bot)
    folder = os.path.join(BOT_ROOT, bot)
    if os.path.exists(folder): shutil.rmtree(folder)
    meta.pop(bot, None)
    save_meta(meta)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
