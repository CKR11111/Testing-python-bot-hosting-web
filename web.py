from flask import Flask, request, render_template, redirect, url_for, jsonify
import os, subprocess, zipfile, shutil, pathlib, time, threading, json, uuid, signal

app = Flask(__name__)

# Directory Setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BOT_ROOT = os.path.join(BASE_DIR, "bots")
META_FILE = os.path.join(BOT_ROOT, "_meta.json")

if not os.path.exists(BOT_ROOT):
    os.makedirs(BOT_ROOT)

running_processes = {} 

def load_meta():
    try:
        if os.path.exists(META_FILE):
            with open(META_FILE, "r") as f: return json.load(f)
    except: pass
    return {}

def save_meta(d):
    with open(META_FILE, "w") as f: json.dump(d, f)

meta = load_meta()

def is_running(bid):
    if bid in running_processes:
        # Check if process is still alive
        if running_processes[bid].poll() is None:
            return True
    return False

@app.route("/api/status")
def api_status():
    out = []
    for bid, info in meta.items():
        out.append({
            "id": bid, 
            "name": info.get("name"), 
            "running": is_running(bid)
        })
    return jsonify(out)

@app.route("/")
def index():
    return render_template("index.html", bots=meta)

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("zipfile")
    auto = request.form.get("autostart") == "1"
    if not f or not f.filename.lower().endswith(".zip"):
        return "Error: Please upload a ZIP file", 400
    
    bid = "inst_" + uuid.uuid4().hex[:6]
    folder = os.path.join(BOT_ROOT, bid)
    os.makedirs(folder, exist_ok=True)
    
    zip_path = os.path.join(BOT_ROOT, f"{bid}.zip")
    f.save(zip_path)
    
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(folder)
        os.remove(zip_path)
    except:
        return "Error: ZIP Extraction Failed", 400
    
    meta[bid] = {"name": pathlib.Path(f.filename).stem, "auto": auto}
    save_meta(meta)
    
    if auto:
        return redirect(url_for("start", bot=bid))
    return redirect(url_for("index"))

@app.route("/start/<bot>")
def start(bot):
    if bot not in meta: return "Not Found", 404
    
    # Stop if already running
    if is_running(bot):
        stop(bot)
    
    folder = os.path.join(BOT_ROOT, bot)
    log_path = os.path.join(folder, "run.log")
    
    # Open log file
    log_file = open(log_path, "a")
    
    # Start process without TMUX (Render Compatible)
    try:
        proc = subprocess.Popen(
            ["python3", "ckr.py"],
            cwd=folder,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True
        )
        running_processes[bot] = proc
    except Exception as e:
        print(f"Error starting bot: {e}")
        
    return redirect(url_for("index"))

@app.route("/stop/<bot>")
def stop(bot):
    if bot in running_processes:
        proc = running_processes[bot]
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            proc.terminate()
        del running_processes[bot]
    return redirect(url_for("index"))

@app.route("/delete/<bot>")
def delete(bot):
    stop(bot)
    folder = os.path.join(BOT_ROOT, bot)
    if os.path.exists(folder):
        shutil.rmtree(folder)
    meta.pop(bot, None)
    save_meta(meta)
    return redirect(url_for("index"))

def watchdog():
    while True:
        for bid, info in list(meta.items()):
            if info.get("auto") and not is_running(bid):
                # Auto-restart logic
                folder = os.path.join(BOT_ROOT, bid)
                log = open(os.path.join(folder, "run.log"), "a")
                try:
                    proc = subprocess.Popen(["python3", "ckr.py"], cwd=folder, stdout=log, stderr=log, start_new_session=True)
                    running_processes[bid] = proc
                except: pass
        time.sleep(15)

threading.Thread(target=watchdog, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
