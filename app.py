# 添加这一行，导入加密函数
from werkzeug.security import generate_password_hash
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Employee, Shift, Attendance
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meiti-shop-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meiti_shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

@login_manager.user_loader
def load_user(user_id):
    return Employee.query.get(int(user_id))

# --- 页面路由 ---
@app.route('/')
def index(): return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        user = Employee.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="用户名或密码错误")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_page'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

# --- API 接口 ---

# 1. 获取员工列表
@app.route('/api/employees', methods=['GET'])
@login_required
def get_employees():
    keyword = request.args.get('search', '')
    
    if current_user.role == 'HR':
        query = Employee.query.filter(Employee.role == 'Depot')
    elif current_user.role == 'Depot':
        query = Employee.query.filter_by(id=current_user.id)
    else:
        return jsonify({"error": "权限不足"}), 403

    if keyword:
        query = query.filter(
            db.or_(
                Employee.name.contains(keyword),
                Employee.username.contains(keyword)
            )
        )

    employees = query.all()
    output = []
    for emp in employees:
        output.append({
            'id': emp.id, 'username': emp.username, 'name': emp.name,
            'hourly_wage': emp.hourly_wage, 'email': emp.email,
            'phone': emp.phone, 'address': emp.address,
            # 🌟 加上新字段
            'emergency_contact': emp.emergency_contact or '',
            'id_card_number': emp.id_card_number or '',
            'department': emp.department or ''
        })
    return jsonify(output)

@app.route('/api/employees/list', methods=['GET'])
@login_required
def get_employee_list():
    # Admin 和 HR 都能调用来显示排班名单
    if current_user.role not in ['Admin', 'HR']: 
        return jsonify({"error": "权限不足"}), 403
    # 获取所有普通员工
    employees = Employee.query.filter_by(role='Depot').all()
    return jsonify([{'id': emp.id, 'name': emp.name} for emp in employees])

# 2. 添加员工 (仅 HR)
@app.route('/api/employees', methods=['POST'])
@login_required
def add_employee():
    if current_user.role != 'HR': return jsonify({"error": "仅 HR 可添加员工"}), 403
    data = request.get_json()
    if Employee.query.filter_by(username=data['username']).first():
        return jsonify({"error": "用户名已存在"}), 400
    
    new_emp = Employee(
        username=data['username'], name=data['name'],
        hourly_wage=float(data.get('hourly_wage', 0.0)), role='Depot'
    )
    new_emp.set_password(data['password'])
    db.session.add(new_emp)
    db.session.commit()
    return jsonify({"message": "添加成功"}), 201

# 3. 删除员工 (有排班不能删)
@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
@login_required
def delete_employee(emp_id):
    if current_user.role != 'HR': return jsonify({"error": "权限不足"}), 403
    emp = Employee.query.get(emp_id)
    if not emp: return jsonify({"error": "员工不存在"}), 404
    
    if len(emp.shifts) > 0 or len(emp.attendances) > 0:
        return jsonify({"error": "该员工存在排班或打卡记录，无法删除！"}), 400
        
    db.session.delete(emp)
    db.session.commit()
    return jsonify({"message": "删除成功"})

# 4. 更新个人信息
@app.route('/api/employee/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json()
    emp = Employee.query.get(current_user.id)
    emp.name = data.get('name', emp.name)
    emp.email = data.get('email', emp.email)
    emp.phone = data.get('phone', emp.phone)
    emp.address = data.get('address', emp.address)
    emp.employee_id_number = data.get('employee_id_number', emp.employee_id_number)
    db.session.commit()
    return jsonify({"message": "更新成功"})

# 5. 排班相关 (仅 HR)
@app.route('/api/shifts', methods=['POST'])
@login_required
def assign_shift():
    if current_user.role not in ['Admin', 'HR', 'Depot']: 
        return jsonify({"error": "权限不足"}), 403
        
    data = request.get_json()
    
    # Admin 和 HR 可以给别人排，普通员工只能给自己排
    emp_id = data['employee_id'] if current_user.role in ['Admin', 'HR'] else current_user.id
    
    # 🔪 检查是否重复排班（注意这行要和上面的语句完全左对齐）
    existing = Shift.query.filter_by(employee_id=emp_id, date=data['date']).first()
    if existing: 
        return jsonify({"error": "该员工在当天已有排班，无法重复排班！"}), 400

    new_shift = Shift(date=data['date'], shift_type=data['shift_type'], employee_id=emp_id)
    db.session.add(new_shift)
    db.session.commit()
    return jsonify({"message": "排班成功"}), 201

@app.route('/api/shifts/all_global', methods=['GET'])
@login_required
def get_global_shifts():
    if current_user.role != 'HR': return jsonify({"error": "权限不足"}), 403
    
    events = []
    att_records = {f"{a.date}_{a.employee_id}": a.timestamp for a in Attendance.query.all()}
    results = db.session.query(Shift, Employee).join(Employee).all()
    
    for s, emp in results:
        check_key = f"{s.date}_{emp.id}"
        s_name = "Morning" if s.shift_type == 'Morning' else ("Afternoon" if s.shift_type == 'Afternoon' else "Night")
        title = f"{emp.name} ({s_name})"
        
        # 如果员工打卡了，HR 也能看到绿色
        color = '#10b981' if check_key in att_records else '#3b82f6'
        if check_key in att_records: title = f"✅ {title}"

        events.append({
            'id': s.id, 
            'title': title,
            'start': s.date,
            'color': color
        })
    return jsonify(events)

@app.route('/api/shifts/<int:emp_id>/all', methods=['GET'])
@login_required
def get_emp_shifts(emp_id):
    if current_user.role not in ['Admin', 'HR'] and current_user.id != emp_id:
        return jsonify({"error": "权限不足"}), 403
        
    shifts = Shift.query.filter_by(employee_id=emp_id).all()
    output = []
    
    # 查出该员工所有的打卡记录
    att_records = {a.date: a.timestamp for a in Attendance.query.filter_by(employee_id=emp_id).all()}
    
    for s in shifts:
        is_attended = s.date in att_records
        output.append({
            'id': s.id, 
            'date': s.date, 
            'type': s.shift_type,
            'is_attended': is_attended,       # 🌟 告诉前端是否已打卡
            'checkin_time': att_records.get(s.date, '') # 🌟 顺便把打卡时间传过去
        })
    return jsonify(output)

@app.route('/api/shifts/batch_delete', methods=['POST'])
@login_required
def batch_delete_shifts():
    if current_user.role != 'HR': return jsonify({"error": "权限不足"}), 403
    ids = request.get_json().get('ids', [])
    Shift.query.filter(Shift.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"message": "删除成功"})

# 6. 打卡相关
@app.route('/api/attendance/checkin', methods=['POST'])
@login_required
def checkin():
    data = request.get_json()
    if Attendance.query.filter_by(employee_id=current_user.id, date=data['date']).first():
        return jsonify({"error": "今天已经打过卡了"}), 400
        
    now = datetime.datetime.now()
    new_att = Attendance(date=data['date'], timestamp=now.strftime("%H:%M"), shift_type=data['shift_type'], employee_id=current_user.id)
    db.session.add(new_att)
    db.session.commit()
    return jsonify({"message": "打卡成功", "time": now.strftime("%H:%M")})

@app.route('/api/attendance/all', methods=['GET'])
@login_required
def get_all_attendance():
    if current_user.role != 'Admin': return jsonify({"error": "权限不足"}), 403
    
    events = []
    # 字典记录谁在哪天打了卡
    att_records = {f"{a.date}_{a.employee_id}": a.timestamp for a in Attendance.query.all()}

    # 遍历所有排班
    all_shifts = db.session.query(Shift, Employee).join(Employee).all()
    for s, emp in all_shifts:
        check_key = f"{s.date}_{emp.id}"
        
        # 拼接标题：员工名 + (班次英文)
        s_name = "Morning" if s.shift_type == 'Morning' else ("Afternoon" if s.shift_type == 'Afternoon' else "Night")
        title = f"{emp.name} ({s_name})"
        
        if check_key in att_records:
            # 已打卡：绿色
            title = f"✅ {title}" 
            color = '#10b981' # 绿色
        else:
            color = '#3b82f6' # 未打卡蓝

        events.append({
            'id': s.id, # 排班ID
            'title': title,
            'start': s.date,
            'color': color,
            'extendedProps': { 'is_attended': check_key in att_records }
        })
    return jsonify(events)

# 修改排班日期
@app.route('/api/shifts/<int:shift_id>', methods=['PUT'])
@login_required
def update_shift(shift_id):
    if current_user.role not in ['Admin', 'HR']: return jsonify({"error": "权限不足"}), 403
    shift = Shift.query.get(shift_id)
    if not shift: return jsonify({"error": "排班不存在"}), 404
    
    data = request.get_json()
    new_date = data.get('date')
    # 防冲突检测
    if Shift.query.filter_by(employee_id=shift.employee_id, date=new_date).first() and new_date != shift.date:
         return jsonify({"error": "该员工在此日期已有排班"}), 400
         
    shift.date = new_date
    db.session.commit()
    return jsonify({"message": "修改成功"})

# 删除单条排班
@app.route('/api/shifts/<int:shift_id>', methods=['DELETE'])
@login_required
def delete_single_shift(shift_id):
    if current_user.role not in ['Admin', 'HR']: return jsonify({"error": "权限不足"}), 403
    shift = Shift.query.get(shift_id)
    if shift:
        db.session.delete(shift)
        db.session.commit()
    return jsonify({"message": "删除成功"})

# --- 初始化数据库 ---
def init_db():
    with app.app_context():
        db.create_all()
        if not Employee.query.filter_by(username='admin').first():
            db.session.add(Employee(username='admin', name='系统管理员', role='Admin', password_hash=generate_password_hash('admin123')))
        if not Employee.query.filter_by(username='HR').first():
            db.session.add(Employee(username='HR', name='人事经理', role='HR', password_hash=generate_password_hash('1')))
        db.session.commit()

        # 供 HR 修改员工信息
@app.route('/api/employees/<int:emp_id>', methods=['PUT'])
@login_required
def update_employee_info(emp_id):
    if current_user.role != 'HR':
        return jsonify({"error": "权限不足，仅 HR 可修改"}), 403
        
    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({"error": "员工不存在"}), 404
        
    data = request.get_json()
    emp.name = data.get('name', emp.name)
    emp.address = data.get('address', emp.address)
    emp.phone = data.get('phone', emp.phone)
    emp.email = data.get('email', emp.email)
    emp.emergency_contact = data.get('emergency_contact', emp.emergency_contact)
    emp.id_card_number = data.get('id_card_number', emp.id_card_number)
    emp.department = data.get('department', emp.department)
    
    # 时薪因为可能是 0，所以用 is not None 来判断
    if data.get('hourly_wage') is not None:
        emp.hourly_wage = float(data.get('hourly_wage'))
        
    db.session.commit()
    return jsonify({"message": "修改成功"})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)