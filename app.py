from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import date, datetime
import os

# --- App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'smartclassroom2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///classroom.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'png', 'jpg', 'jpeg', 'txt'}

os.makedirs('uploads', exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100))
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    teacher = db.relationship('User', backref='timetables')
    day = db.Column(db.String(20))
    start_time = db.Column(db.String(10))
    end_time = db.Column(db.String(10))
    room = db.Column(db.String(50))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    student = db.relationship('User', backref='attendances')
    subject = db.Column(db.String(100))
    date = db.Column(db.String(20))
    status = db.Column(db.String(10))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    notif_type = db.Column(db.String(20))
    timestamp = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    posted_by = db.relationship('User', backref='notifications')

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    subject = db.Column(db.String(100))
    description = db.Column(db.Text)
    filename = db.Column(db.String(200))
    timestamp = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_by = db.relationship('User', backref='notes')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/manage')
@login_required
def manage():
    users = User.query.all()
    return render_template('manage.html', users=users)

@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']
    if User.query.filter_by(email=email).first():
        flash('Email already exists!')
        return redirect(url_for('manage'))
    new_user = User(
        name=name,
        email=email,
        password=generate_password_hash(password),
        role=role
    )
    db.session.add(new_user)
    db.session.commit()
    flash(f'{role.capitalize()} "{name}" added successfully!')
    return redirect(url_for('manage'))

@app.route('/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted!')
    return redirect(url_for('manage'))

@app.route('/timetable')
@login_required
def timetable():
    entries = Timetable.query.all()
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('timetable.html', entries=entries, teachers=teachers)

@app.route('/add_timetable', methods=['POST'])
@login_required
def add_timetable():
    entry = Timetable(
        subject=request.form['subject'],
        teacher_id=request.form['teacher_id'],
        day=request.form['day'],
        start_time=request.form['start_time'],
        end_time=request.form['end_time'],
        room=request.form['room']
    )
    db.session.add(entry)
    db.session.commit()
    flash('Class added to timetable!')
    return redirect(url_for('timetable'))

@app.route('/delete_timetable/<int:entry_id>')
@login_required
def delete_timetable(entry_id):
    entry = Timetable.query.get(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash('Class deleted!')
    return redirect(url_for('timetable'))

@app.route('/attendance')
@login_required
def attendance():
    students = User.query.filter_by(role='student').all()
    records = Attendance.query.order_by(Attendance.id.desc()).limit(20).all()
    today = str(date.today())
    total_students = len(students)
    present_today = Attendance.query.filter_by(date=today, status='Present').count()
    absent_today = Attendance.query.filter_by(date=today, status='Absent').count()
    return render_template('attendance.html',
        students=students,
        records=records,
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today
    )

@app.route('/mark_attendance', methods=['POST'])
@login_required
def mark_attendance():
    record = Attendance(
        student_id=request.form['student_id'],
        subject=request.form['subject'],
        date=request.form['date'],
        status=request.form['status']
    )
    db.session.add(record)
    db.session.commit()
    flash('Attendance marked successfully!')
    return redirect(url_for('attendance'))

@app.route('/notifications')
@login_required
def notifications():
    all_notifs = Notification.query.order_by(Notification.id.desc()).all()
    return render_template('notifications.html', notifications=all_notifs)

@app.route('/post_notification', methods=['POST'])
@login_required
def post_notification():
    notif = Notification(
        title=request.form['title'],
        message=request.form['message'],
        notif_type=request.form['notif_type'],
        timestamp=datetime.now().strftime('%d %b %Y, %I:%M %p'),
        user_id=current_user.id
    )
    db.session.add(notif)
    db.session.commit()
    flash('Notification posted successfully!')
    return redirect(url_for('notifications'))

@app.route('/delete_notification/<int:notif_id>')
@login_required
def delete_notification(notif_id):
    notif = Notification.query.get(notif_id)
    db.session.delete(notif)
    db.session.commit()
    flash('Notification deleted!')
    return redirect(url_for('notifications'))

@app.route('/analytics')
@login_required
def analytics():
    students = User.query.filter_by(role='student').all()
    analytics_data = []
    good_count = 0
    average_count = 0
    risk_count = 0
    for student in students:
        total = Attendance.query.filter_by(student_id=student.id).count()
        present = Attendance.query.filter_by(student_id=student.id, status='Present').count()
        pct = round((present / total) * 100) if total > 0 else 0
        if pct >= 75:
            status_class = 'good'
            prediction = 'Likely to perform well'
            good_count += 1
        elif pct >= 50:
            status_class = 'average'
            prediction = 'Needs improvement'
            average_count += 1
        else:
            status_class = 'risk'
            prediction = 'At risk - Immediate attention needed'
            risk_count += 1
        analytics_data.append({
            'name': student.name,
            'email': student.email,
            'total': total,
            'present': present,
            'attendance_pct': pct,
            'status_class': status_class,
            'prediction': prediction
        })
    return render_template('analytics.html',
        analytics=analytics_data,
        total_students=len(students),
        good_count=good_count,
        average_count=average_count,
        risk_count=risk_count
    )

@app.route('/notes')
@login_required
def notes():
    all_notes = Note.query.order_by(Note.id.desc()).all()
    return render_template('notes.html', notes=all_notes)

@app.route('/upload_note', methods=['POST'])
@login_required
def upload_note():
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        note = Note(
            title=request.form['title'],
            subject=request.form['subject'],
            description=request.form['description'],
            filename=filename,
            timestamp=datetime.now().strftime('%d %b %Y, %I:%M %p'),
            user_id=current_user.id
        )
        db.session.add(note)
        db.session.commit()
        flash('Note uploaded successfully!')
    else:
        flash('Invalid file type!')
    return redirect(url_for('notes'))

@app.route('/download_note/<int:note_id>')
@login_required
def download_note(note_id):
    note = Note.query.get(note_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], note.filename, as_attachment=True)

@app.route('/delete_note/<int:note_id>')
@login_required
def delete_note(note_id):
    note = Note.query.get(note_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], note.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted!')
    return redirect(url_for('notes'))

# --- Create DB and Admin User ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@school.com').first():
        admin = User(
            name='Admin',
            email='admin@school.com',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)