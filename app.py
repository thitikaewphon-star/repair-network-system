import os
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ฟังก์ชันเชื่อมต่อฐานข้อมูล
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# ฟังก์ชันสร้างตารางเริ่มต้นอัตโนมัติ
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_name TEXT NOT NULL,
            problem TEXT NOT NULL,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 1. เช็กสิทธิ์แอดมิน (แก้รหัสผ่านเป็น 1234 ตรงนี้แล้วครับ)
        if username == 'admin' and password == '1234':
            session['user'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('dashboard'))
        
        # 2. ถ้าไม่ใช่แอดมิน แต่มีการกรอกข้อมูลมา ให้เป็น User ทั่วไป (ใส่อะไรก็ได้)
        elif username and password:
            session['user'] = username
            session['role'] = 'user'
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='กรุณากรอกชื่อผู้ใช้และรหัสผ่าน')
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        devices = conn.execute('SELECT * FROM devices').fetchall()
        conn.close()
    except Exception:
        devices = []
        
    return render_template('dashboard.html', devices=devices, role=session.get('role'))

@app.route('/repair', methods=['GET', 'POST'])
def repair():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        device_name = request.form.get('device_name')
        problem = request.form.get('problem')
        
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO repairs (device_name, problem, status) VALUES (?, ?, ?)', 
                         (device_name, problem, 'Pending'))
            conn.commit()
            conn.close()
        except Exception as e:
            print("Repair Error:", e)
            
        return redirect(url_for('repair'))
        
    return render_template('repair.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)