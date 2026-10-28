from flask_sqlalchemy import SQLAlchemyfrom flask_login import UserMixinfrom werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
class Employee(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    employee_id_number = db.Column(db.String(20))
    hourly_wage = db.Column(db.Float, default=0.0)
    role = db.Column(db.String(20), default='Store Employee')
    emergency_contact = db.Column(db.String(100))
    id_card_number = db.Column(db.String(30))
    department = db.Column(db.String(50))
    avatar = db.Column(db.String(200), default='default_avatar.png')

    shifts = db.relationship('Shift', backref='employee', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('Attendance', backref='employee', lazy=True, cascade="all, delete-orphan")
    work_logs = db.relationship('WorkLog', backref='employee', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    shift_type = db.Column(db.String(20), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    status = db.Column(db.String(20), default='Approved') 
# class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.String(20), nullable=False)
    shift_type = db.Column(db.String(20), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
class WorkLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    shift_type = db.Column(db.String(20), nullable=False)
    check_in = db.Column(db.String(20))
    check_out = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Normal')
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
