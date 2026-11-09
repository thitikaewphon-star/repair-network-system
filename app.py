@app.route('/login', methods=['GET', 'POST'])
def login():
    session.clear()
    
    if request.method == 'POST':
        # ใช้ .strip() เพื่อตัดช่องว่างที่อาจติดมาจากการพิมพ์หรือออโต้ฟิลออกทั้งหมด
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # เช็กสิทธิ์แอดมิน
        if username == 'admin' and password == '1234':
            session['user'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('dashboard'))
        
        # ผู้ใช้ทั่วไป
        elif username and password:
            session['user'] = username
            session['role'] = 'user'
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='กรุณากรอกชื่อผู้ใช้และรหัสผ่าน')
            
    return render_template('login.html')