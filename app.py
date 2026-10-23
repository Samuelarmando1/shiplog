from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
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

class User(UserMixin, db.Model):
    __tablename__ = 'tmp_empleados'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    logs = db.relationship('Log', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('tmp_empleados.id'), nullable=False)
    files = db.relationship('File', backref='log', lazy=True, cascade='all, delete-orphan')

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    log_id = db.Column(db.Integer, db.ForeignKey('log.id'), nullable=False)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if current_user.is_authenticated:
        logs = Log.query.filter_by(user_id=current_user.id).order_by(Log.date.desc()).all()
        return render_template('index.html', logs=logs)
    return redirect(url_for('login'))

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
        
        if User.query.filter_by(username=username).first():
            flash('El usuario ya existe', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username)
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
        is_admin = request.form.get('is_admin') == 'on'
        
        if User.query.filter_by(username=username).first():
            flash('El usuario ya existe', 'danger')
            return redirect(url_for('admin_create_user'))
        
        user = User(username=username, is_admin=is_admin)
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
        
        log = Log(title=title, content=content, user_id=current_user.id)
        db.session.add(log)
        db.session.commit()
        
        # Manejar archivos subidos
        files = request.files.getlist('files')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Agregar timestamp para evitar nombres duplicados
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                file_record = File(filename=filename, original_name=file.filename, log_id=log.id)
                db.session.add(file_record)
        
        db.session.commit()
        flash('Log creado exitosamente!', 'success')
        return redirect(url_for('index'))
    
    return render_template('create.html')

@app.route('/log/<int:log_id>')
@login_required
def view_log(log_id):
    log = Log.query.get_or_404(log_id)
    if log.user_id != current_user.id:
        flash('No tienes permiso para ver este log', 'danger')
        return redirect(url_for('index'))
    return render_template('view.html', log=log)

@app.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_log(log_id):
    log = Log.query.get_or_404(log_id)
    
    if log.user_id != current_user.id:
        flash('No tienes permiso para eliminar este log', 'danger')
        return redirect(url_for('index'))
    
    # Eliminar archivos físicos
    for file in log.files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.session.delete(log)
    db.session.commit()
    flash('Log eliminado exitosamente!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
