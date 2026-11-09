import os
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # กำหนด Secret Key สำหรับจัดการ Session

# ฟังก์ชันเชื่อมต่อฐานข้อมูล SQLite
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# หน้าแรก (Redirect ไปหน้า Login)
@app.route('/')
def index():
    return redirect(url_for('login'))

# หน้า Login (เข้าสู่ระบบ)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # ตัวอย่างตรวจสอบล็อกอินพื้นฐาน (สามารถปรับเปลี่ยนตามโครงสร้างตาราง user ของคุณได้เลยครับ)
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user or (username == 'admin' and password == 'admin'): # เผื่อกรณีใช้บัญชีแอดมินทดสอบ
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
            
    return render_template('login.html')

# หน้า Dashboard (หน้าหลักหลังเข้าสู่ระบบ)
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    devices = conn.execute('SELECT * FROM devices').fetchall() if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'").fetchone() else []
    conn.close()
    
    return render_template('dashboard.html', devices=devices)

# หน้าจัดการแจ้งซ่อม (Repair)
@app.route('/repair', methods=['GET', 'POST'])
def repair():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        # รับค่าจากฟอร์มแจ้งซ่อม
        device_name = request.form.get('device_name')
        problem = request.form.get('problem')
        
        conn = get_db_connection()
        # ตัวอย่างบันทึกข้อมูลลงฐานข้อมูล (ปรับชื่อตารางตามจริงของคุณได้เลย)
        try:
            conn.execute('INSERT INTO repairs (device_name, problem, status) VALUES (?, ?, ?)', 
                         (device_name, problem, 'Pending'))
            conn.commit()
        except Exception as e:
            print("Error:", e)
        finally:
            conn.close()
            
        return redirect(url_for('repair'))
        
    return render_template('repair.html')

# หน้า Logout (ออกจากระบบ)
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    # ดึงค่า PORT จาก Render หรือใช้พอร์ต 5000 เป็นค่าเริ่มต้นสำหรับการรันในเครื่อง
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)