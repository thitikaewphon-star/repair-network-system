from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import sqlite3
import os
import subprocess
import re
import json
from pathlib import Path
from functools import wraps
from datetime import datetime
from werkzeug.utils import secure_filename

from devices import devices as initial_devices

app = Flask(__name__)
app.secret_key = "cyber-command-repair-network-secret-key"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "devices_data.json"

# --- ฐานข้อมูลแจ้งซ่อม (SQLite) ---
def init_sqlite_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repair_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment TEXT NOT NULL,
            category TEXT DEFAULT 'คอมพิวเตอร์',
            location TEXT NOT NULL,
            problem TEXT NOT NULL,
            reporter TEXT NOT NULL,
            status TEXT DEFAULT 'รอดำเนินการ',
            admin_note TEXT DEFAULT '',
            image TEXT DEFAULT '',
            repair_cost REAL DEFAULT 0.0
        )
    ''')
    for col, col_type in [('category', 'TEXT DEFAULT "คอมพิวเตอร์"'), ('admin_note', 'TEXT DEFAULT ""'), ('image', 'TEXT DEFAULT ""'), ('repair_cost', 'REAL DEFAULT 0.0')]:
        try:
            cursor.execute(f"ALTER TABLE repair_reports ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

init_sqlite_db()

# --- ระบบจัดการ JSON เครือข่าย ---
def load_devices():
    if not DATA_FILE.exists():
        save_devices(initial_devices)
        return [dict(d) for d in initial_devices]
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [dict(d) for d in initial_devices]
    except (json.JSONDecodeError, OSError):
        return [dict(d) for d in initial_devices]

def save_devices(data):
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return jsonify({"success": False, "message": "เฉพาะผู้ดูแลระบบเท่านั้น"}), 403
        return fn(*args, **kwargs)
    return wrapper

def check_device(ip):
    """ตรวจสอบอุปกรณ์ด้วย ping สำหรับ Windows"""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1000", str(ip)],
            capture_output=True,
            text=True,
            encoding="cp874",
            errors="ignore",
            timeout=3
        )
        output = result.stdout or ""
        match = re.search(r"time[=<]\s*(\d+)\s*ms", output, re.IGNORECASE)
        if match:
            ping = int(match.group(1))
            return "Online", max(ping, 1)
        if "TTL=" in output.upper():
            return "Online", 1
        return "Offline", 0
    except (subprocess.TimeoutExpired, OSError):
        return "Offline", 0

@app.before_request
def require_login():
    allowed = {"login", "static"}
    if request.endpoint in allowed:
        return
    if "username" not in session:
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        
        if username:
            session.clear()
            session["username"] = username
            if username == "admin":
                session["role"] = "admin"
                session["display"] = "ผู้ดูแลระบบ"
            else:
                session["role"] = "user"
                session["display"] = username.capitalize()
            return redirect(url_for("dashboard"))
        
        else:
            return render_template("login.html", error="กรุณากรอกชื่อผู้ใช้งาน")

    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    return render_template('dashboard.html', 
                           username=session.get("username"),
                           display=session.get("display"),
                           role=session.get("role"))

@app.route("/")
def root_redirect():
    return redirect(url_for("dashboard"))

# --- ระบบแจ้งซ่อม ---
@app.route('/repair', methods=['GET', 'POST'])
def repair_system():
    is_admin = session.get('username', '').lower() == 'admin'
    
    if request.method == 'POST':
        if is_admin:
            return redirect(url_for('repair_system'))
            
        equipment = request.form.get('equipment', '')
        category = request.form.get('category', 'คอมพิวเตอร์')
        location = request.form.get('location', '')
        problem = request.form.get('problem', '')
        reporter = request.form.get('reporter', '')
        
        image_filename = ''
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO repair_reports (equipment, category, location, problem, reporter, image) VALUES (?, ?, ?, ?, ?, ?)",
                       (equipment, category, location, problem, reporter, image_filename))
        conn.commit()
        conn.close()
        return redirect(url_for('repair_system'))
    
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repair_reports ORDER BY id DESC")
    reports = cursor.fetchall()
    
    total_cases = len(reports)
    completed_cases = sum(1 for r in reports if r['status'] == 'ซ่อมเสร็จสิ้น')
    pending_cases = sum(1 for r in reports if r['status'] == 'รอดำเนินการ')
    total_cost = sum(r['repair_cost'] for r in reports if r['repair_cost'] is not None)
    
    conn.close()
    
    return render_template('repair.html', reports=reports, is_admin=is_admin, active_tab='repair',
                           total_cases=total_cases, completed_cases=completed_cases,
                           pending_cases=pending_cases, total_cost=total_cost)

@app.route('/admin')
def admin_panel():
    if session.get('username', '').lower() != 'admin':
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repair_reports ORDER BY id DESC")
    reports = cursor.fetchall()
    
    total_cases = len(reports)
    completed_cases = sum(1 for r in reports if r['status'] == 'ซ่อมเสร็จสิ้น')
    pending_cases = sum(1 for r in reports if r['status'] == 'รอดำเนินการ')
    total_cost = sum(r['repair_cost'] for r in reports if r['repair_cost'] is not None)
    
    conn.close()
    
    return render_template('repair.html', reports=reports, is_admin=True, active_tab='repair',
                           total_cases=total_cases, completed_cases=completed_cases,
                           pending_cases=pending_cases, total_cost=total_cost)

@app.route('/update_repair/<int:id>', methods=['POST'])
def update_repair(id):
    if session.get('username', '').lower() == 'admin':
        status = request.form.get('status', 'รอดำเนินการ')
        admin_note = request.form.get('admin_note', '')
        cost_str = request.form.get('repair_cost', '0')
        try:
            repair_cost = float(cost_str)
        except ValueError:
            repair_cost = 0.0
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE repair_reports SET status = ?, admin_note = ?, repair_cost = ? WHERE id = ?", 
                       (status, admin_note, repair_cost, id))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_panel'))
    return redirect(url_for('login'))

# --- ระบบตรวจสอบเครือข่าย ---
@app.route('/network')
def network_system():
    return render_template(
        "index.html",
        username=session.get("username"),
        display=session.get("display"),
        role=session.get("role"),
        is_admin=session.get("role") == "admin",
    )

@app.route("/api/devices")
def api_devices():
    data = load_devices()
    result = []
    for i, device in enumerate(data):
        item = dict(device)
        item["id"] = i
        if device.get("unknown", False):
            item["status"] = "Unknown"
            item["ping"] = 0
        else:
            status, ping = check_device(device.get("ip", ""))
            item["status"] = status
            item["ping"] = ping
        item.setdefault("type", "Network Device")
        item.setdefault("location", "-")
        item.setdefault("building", "-")
        result.append(item)
    return jsonify(result)

@app.route("/api/devices", methods=["POST"])
@admin_required
def add_device():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    ip = str(payload.get("ip", "")).strip()
    if not name or not ip:
        return jsonify({"success": False, "message": "กรุณากรอกชื่ออุปกรณ์และ IP"}), 400

    data = load_devices()
    data.append({
        "name": name,
        "ip": ip,
        "type": str(payload.get("type", "Network Device")).strip() or "Network Device",
        "location": str(payload.get("location", "-")).strip() or "-",
        "building": str(payload.get("building", "-")).strip() or "-",
        "unknown": bool(payload.get("unknown", False)),
    })
    save_devices(data)
    return jsonify({"success": True, "message": "เพิ่มอุปกรณ์เรียบร้อย"})

@app.route("/api/devices/<int:device_id>", methods=["PUT"])
@admin_required
def update_device(device_id):
    payload = request.get_json(silent=True) or {}
    data = load_devices()
    if device_id < 0 or device_id >= len(data):
        return jsonify({"success": False, "message": "ไม่พบอุปกรณ์"}), 404

    name = str(payload.get("name", "")).strip()
    ip = str(payload.get("ip", "")).strip()
    if not name or not ip:
        return jsonify({"success": False, "message": "ชื่ออุปกรณ์และ IP ห้ามว่าง"}), 400

    data[device_id] = {
        "name": name,
        "ip": ip,
        "type": str(payload.get("type", "Network Device")).strip() or "Network Device",
        "location": str(payload.get("location", "-")).strip() or "-",
        "building": str(payload.get("building", "-")).strip() or "-",
        "unknown": bool(payload.get("unknown", False)),
    }
    save_devices(data)
    return jsonify({"success": True, "message": "แก้ไขข้อมูลเรียบร้อย"})

@app.route("/api/devices/<int:device_id>", methods=["DELETE"])
@admin_required
def delete_device(device_id):
    data = load_devices()
    if device_id < 0 or device_id >= len(data):
        return jsonify({"success": False, "message": "ไม่พบอุปกรณ์"}), 404

    removed = data.pop(device_id)
    save_devices(data)
    return jsonify({"success": True, "message": f"ลบ {removed.get('name', 'อุปกรณ์')} เรียบร้อย"})

@app.route("/api/me")
def api_me():
    return jsonify({
        "username": session.get("username"),
        "display": session.get("display"),
        "role": session.get("role"),
        "is_admin": session.get("role") == "admin",
        "time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    })

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)