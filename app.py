from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, date
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'tu-clave-secreta-aqui-cambiala-despues')
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip'}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@app.template_filter('minutes_to_hours')
def minutes_to_hours(minutes):
    """Convierte minutos a formato HH:MM"""
    if not minutes:
        return "0h 0m"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{mins}m"

class User(UserMixin, db.Model):
    __tablename__ = 'tmp_empleados'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    name_employee = db.Column(db.String(100), nullable=False)
    fech_alta = db.Column(db.DateTime, default=datetime.utcnow)
    actividades = db.relationship('Actividad', backref='author', lazy=True)
    dias = db.relationship('Dia', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Actividad(db.Model):
    __tablename__ = 'ctl_actividades'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    tiempo = db.Column(db.Integer, nullable=False)
    dias = db.Column(db.Integer, default=0)
    horas = db.Column(db.Integer, default=0)
    minutos = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('tmp_empleados.id'), nullable=False)
    dia_id = db.Column(db.Integer, db.ForeignKey('ctl_dias.id'), nullable=False)
    files = db.relationship('File', backref='actividad', lazy=True, cascade='all, delete-orphan')

class Dia(db.Model):
    __tablename__ = 'ctl_dias'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('tmp_empleados.id'), nullable=False)
    actividades = db.relationship('Actividad', backref='dia', lazy=True)
    __table_args__ = (db.UniqueConstraint('fecha', 'user_id', name='uq_fecha_user'),)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    actividad_id = db.Column(db.Integer, db.ForeignKey('ctl_actividades.id'), nullable=False)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if current_user.is_authenticated:
        from datetime import timedelta
        today = date.today()
        last_week = today - timedelta(days=6)

        dias = Dia.query.filter(
            Dia.user_id == current_user.id,
            Dia.fecha >= last_week,
            Dia.fecha <= today
        ).order_by(Dia.fecha.desc()).all()

        return render_template('index.html', dias=dias, today=today)
    return redirect(url_for('login'))

@app.route('/todos-dias')
@login_required
def todos_dias():
    dias = Dia.query.filter_by(user_id=current_user.id).order_by(Dia.fecha.desc()).all()
    return render_template('todos_dias.html', dias=dias)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('¡Bienvenido de nuevo!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name_employee = request.form['name_employee']

        if User.query.filter_by(username=username).first():
            flash('El usuario ya existe', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, name_employee=name_employee)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('¡Registro exitoso! Ahora puedes iniciar sesión', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/admin/create-user', methods=['GET', 'POST'])
@login_required
def admin_create_user():
    if not current_user.is_admin:
        flash('No tienes permiso para acceder a esta página', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name_employee = request.form['name_employee']
        is_admin = request.form.get('is_admin') == 'on'

        if User.query.filter_by(username=username).first():
            flash('El usuario ya existe', 'danger')
            return redirect(url_for('admin_create_user'))

        user = User(username=username, name_employee=name_employee, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'Usuario {username} creado exitosamente!', 'success')
        return redirect(url_for('index'))

    return render_template('admin_create_user.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        
        if user:
            return redirect(url_for('reset_password', username=username))
        else:
            flash('El usuario no existe', 'danger')
            return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<username>', methods=['GET', 'POST'])
def reset_password(username):
    user = User.query.filter_by(username=username).first()
    
    if not user:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('reset_password', username=username))
        
        user.set_password(new_password)
        db.session.commit()
        
        flash('¡Contraseña cambiada exitosamente! Ahora puedes iniciar sesión', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', username=username)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tiempo = int(request.form['tiempo'])
        fecha_actividad = request.form.get('fecha') or date.today()

        fecha_actividad = datetime.strptime(fecha_actividad, '%Y-%m-%d').date() if isinstance(fecha_actividad, str) else fecha_actividad

        dia = Dia.query.filter_by(fecha=fecha_actividad, user_id=current_user.id).first()
        if not dia:
            dia = Dia(fecha=fecha_actividad, user_id=current_user.id)
            db.session.add(dia)
            db.session.commit()

        # Calcular días, horas y minutos
        dias = tiempo // 540  # 540 minutos = 9 horas = 1 día
        minutos_restantes = tiempo % 540
        horas = minutos_restantes // 60
        minutos = minutos_restantes % 60

        actividad = Actividad(title=title, content=content, tiempo=tiempo, dias=dias, horas=horas, minutos=minutos, user_id=current_user.id, dia_id=dia.id)
        db.session.add(actividad)
        db.session.commit()

        files = request.files.getlist('files')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                file_record = File(filename=filename, original_name=file.filename, actividad_id=actividad.id)
                db.session.add(file_record)

        db.session.commit()
        flash('Actividad creada exitosamente!', 'success')
        return redirect(url_for('index'))

    return render_template('create.html', today=date.today())

@app.route('/dia/<int:dia_id>')
@login_required
def view_dia(dia_id):
    dia = Dia.query.get_or_404(dia_id)
    if dia.user_id != current_user.id:
        flash('No tienes permiso para ver este día', 'danger')
        return redirect(url_for('index'))
    return render_template('view_dia.html', dia=dia)

@app.route('/actividad/<int:actividad_id>')
@login_required
def view_actividad(actividad_id):
    actividad = Actividad.query.get_or_404(actividad_id)
    if actividad.user_id != current_user.id:
        flash('No tienes permiso para ver esta actividad', 'danger')
        return redirect(url_for('index'))
    return render_template('view.html', actividad=actividad)

@app.route('/actividad/<int:actividad_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_actividad(actividad_id):
    actividad = Actividad.query.get_or_404(actividad_id)
    if actividad.user_id != current_user.id:
        flash('No tienes permiso para editar esta actividad', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        actividad.title = request.form['title']
        actividad.content = request.form['content']
        tiempo = int(request.form['tiempo'])
        actividad.tiempo = tiempo
        fecha_actividad = request.form.get('fecha') or date.today()

        fecha_actividad = datetime.strptime(fecha_actividad, '%Y-%m-%d').date() if isinstance(fecha_actividad, str) else fecha_actividad

        # Calcular días, horas y minutos
        dias = tiempo // 540  # 540 minutos = 9 horas = 1 día
        minutos_restantes = tiempo % 540
        horas = minutos_restantes // 60
        minutos = minutos_restantes % 60

        actividad.dias = dias
        actividad.horas = horas
        actividad.minutos = minutos

        if actividad.dia.fecha != fecha_actividad:
            dia_nuevo = Dia.query.filter_by(fecha=fecha_actividad, user_id=current_user.id).first()
            if not dia_nuevo:
                dia_nuevo = Dia(fecha=fecha_actividad, user_id=current_user.id)
                db.session.add(dia_nuevo)
                db.session.commit()

            actividad.dia_id = dia_nuevo.id
            actividad.date = datetime.combine(fecha_actividad, datetime.now().time())

        db.session.commit()
        flash('Actividad actualizada exitosamente!', 'success')
        return redirect(url_for('view_dia', dia_id=actividad.dia_id))

    return render_template('edit.html', actividad=actividad)

@app.route('/actividad/<int:actividad_id>/delete', methods=['POST'])
@login_required
def delete_actividad(actividad_id):
    actividad = Actividad.query.get_or_404(actividad_id)
    
    if actividad.user_id != current_user.id:
        flash('No tienes permiso para eliminar esta actividad', 'danger')
        return redirect(url_for('index'))
    
    # Eliminar archivos físicos
    for file in actividad.files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.session.delete(actividad)
    db.session.commit()
    flash('Actividad eliminada exitosamente!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
