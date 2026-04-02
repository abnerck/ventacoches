from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, TextAreaField, IntegerField, SelectField, SubmitField, FileField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import shutil
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# SQLite en instance/ (convención Flask). Si aún tienes cars.db en la raíz del proyecto, se copia una vez.
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
_INSTANCE_DIR = os.path.join(_APP_ROOT, 'instance')
os.makedirs(_INSTANCE_DIR, exist_ok=True)
_DB_INSTANCE = os.path.join(_INSTANCE_DIR, 'cars.db')
_DB_LEGACY = os.path.join(_APP_ROOT, 'cars.db')
if not os.path.isfile(_DB_INSTANCE) and os.path.isfile(_DB_LEGACY):
    shutil.copy2(_DB_LEGACY, _DB_INSTANCE)
    print('BD: migrada cars.db → instance/cars.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + _DB_INSTANCE.replace('\\', '/')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración para subida de imágenes
# Ruta absoluta: las subidas coinciden siempre con /static/... del servidor
app.config['UPLOAD_FOLDER'] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'cars'
)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'


from twilio.rest import Client


def enviar_whatsapp(numero, mensaje):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_whatsapp = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
    if not account_sid or not auth_token:
        raise RuntimeError('Configura TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN en .env')
    client = Client(account_sid, auth_token)
    client.messages.create(
        from_=from_whatsapp,
        to=f'whatsapp:{numero}',
        body=mensaje
    )

@app.route("/api/test-whatsapp", methods=['GET'])
@login_required
def test_whatsapp():
    if not current_user.is_admin:
        abort(403)
    try:
        destino = os.getenv('TWILIO_TEST_WHATSAPP_TO', '').strip()
        if not destino:
            return jsonify({'error': 'Configura TWILIO_TEST_WHATSAPP_TO en .env (ej. +521234567890)'}), 400
        enviar_whatsapp(destino, 'Hola! Prueba desde Flask 🎉')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Función para verificar extensiones de archivo
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def safe_redirect_target(target):
    """Evita open redirect tras login: solo rutas relativas del mismo sitio."""
    if not target or not isinstance(target, str):
        return None
    t = target.strip()
    if t.startswith('/') and not t.startswith('//') and '\n' not in t and '\r' not in t:
        return t
    return None

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    email = db.Column(db.String(120), nullable=True)

class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    marca = db.Column(db.String(100), nullable=False)
    modelo = db.Column(db.String(100), nullable=False)
    año = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    kilometraje = db.Column(db.Integer)
    tipo_combustible = db.Column(db.String(50))
    descripcion = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    activo = db.Column(db.Boolean, default=True)
    # Relación con las fotos (una para muchas)
    fotos = db.relationship('CarPhoto', backref='car', lazy=True, cascade='all, delete-orphan')

class CarPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'), nullable=False)
    filename = db.Column(db.String(500), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)  # Foto principal
    orden = db.Column(db.Integer, default=0)  # Orden de visualización
    fecha_subida = db.Column(db.DateTime, default=db.func.current_timestamp())

# Forms
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Contraseña actual', validators=[DataRequired()])
    new_password = PasswordField(
        'Nueva contraseña',
        validators=[DataRequired(), Length(min=8, max=128, message='Entre 8 y 128 caracteres.')],
    )
    new_password2 = PasswordField(
        'Confirmar nueva contraseña',
        validators=[DataRequired(), EqualTo('new_password', message='Las contraseñas nuevas no coinciden.')],
    )
    submit = SubmitField('Actualizar contraseña')


class ChangeUsernameForm(FlaskForm):
    new_username = StringField(
        'Nuevo nombre de usuario',
        validators=[DataRequired(), Length(min=3, max=80, message='Entre 3 y 80 caracteres.')],
    )
    current_password = PasswordField('Contraseña actual', validators=[DataRequired()])
    submit = SubmitField('Cambiar usuario')


class ChangeEmailForm(FlaskForm):
    email = StringField(
        'Correo electrónico',
        validators=[Optional(), Length(max=120), Email(message='Introduce un correo válido.')],
    )
    current_password = PasswordField('Contraseña actual', validators=[DataRequired()])
    submit = SubmitField('Guardar correo')


class CarForm(FlaskForm):
    marca = StringField('Marca', validators=[DataRequired(), Length(min=2, max=100, message='Entre 2 y 100 caracteres.')])
    modelo = StringField('Modelo', validators=[DataRequired(), Length(min=2, max=100, message='Entre 2 y 100 caracteres.')])
    año = IntegerField('Año', validators=[DataRequired(), NumberRange(min=1900, max=2030, message='Año entre 1900 y 2030.')])
    precio = FloatField(
        'Precio (MXN)',
        validators=[DataRequired(), NumberRange(min=0, max=99_999_999.99, message='Precio no válido.')],
    )
    kilometraje = IntegerField(
        'Kilometraje (km)',
        validators=[Optional(), NumberRange(min=0, max=2_000_000, message='Kilometraje no válido.')],
    )
    tipo_combustible = SelectField('Combustible', choices=[
        ('gasolina', 'Gasolina'),
        ('diesel', 'Diésel'),
        ('hibrido', 'Híbrido'),
        ('electrico', 'Eléctrico')
    ])
    descripcion = TextAreaField('Descripción', validators=[Optional(), Length(max=20000, message='Máximo 20.000 caracteres.')])
    submit = SubmitField('Guardar Coche')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Crear usuario admin por defecto
def create_admin_user():
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado: admin / admin123")


def ensure_user_email_column():
    """SQLite: añade columna email a user si no existe."""
    try:
        insp = inspect(db.engine)
        if 'user' not in insp.get_table_names():
            return
        cols = {c['name'] for c in insp.get_columns('user')}
        if 'email' in cols:
            return
        db.session.execute(text('ALTER TABLE user ADD COLUMN email VARCHAR(120)'))
        db.session.commit()
    except Exception:
        pass


# Función para guardar imágenes
def save_car_photos(car_id, files):
    saved_filenames = []
    existing_count = CarPhoto.query.filter_by(car_id=car_id).count()

    for i, file in enumerate(files):
        if not file or not file.filename or not allowed_file(file.filename):
            continue
        original_name = secure_filename(file.filename)
        if not original_name:
            continue
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"{timestamp}_{original_name}"

        car_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(car_id))
        os.makedirs(car_folder, exist_ok=True)

        file_path = os.path.join(car_folder, filename)
        file.save(file_path)

        # Solo la primera foto del coche (en cualquier subida) es principal
        is_primary = existing_count == 0 and i == 0
        orden = existing_count + i

        photo = CarPhoto(
            car_id=car_id,
            filename=filename,
            is_primary=is_primary,
            orden=orden,
        )
        db.session.add(photo)
        saved_filenames.append(filename)

    if saved_filenames:
        db.session.commit()

    return saved_filenames

# Función para obtener la URL de una foto
def get_photo_url(car_id, filename):
    return f"/static/uploads/cars/{car_id}/{filename}"

# Función para obtener la foto principal de un coche
def get_primary_photo_url(car):
    if car.fotos:
        primary_photo = next((p for p in car.fotos if p.is_primary), car.fotos[0])
        return get_photo_url(car.id, primary_photo.filename)
    return None

# Rutas públicas
@app.route("/")
@app.route("/gestorianacional")
def gestoria():
    """Página principal: Gestoría Nacional (trámites)."""
    return render_template("gestoria.html")


@app.route("/inicio")
def home():
    """Vitrina con últimas incorporaciones (coches)."""
    cars = Car.query.filter_by(activo=True).order_by(Car.fecha_creacion.desc()).limit(6).all()
    for car in cars:
        car.photo_url = get_primary_photo_url(car)
    return render_template("index.html", cars=cars)

@app.route("/coches")
def public_cars():
    page = request.args.get('page', 1, type=int) or 1
    if page < 1:
        page = 1
    cars = Car.query.filter_by(activo=True).order_by(Car.fecha_creacion.desc()).paginate(page=page, per_page=9)
    # Añadir URL de foto principal a cada coche
    for car in cars.items:
        car.photo_url = get_primary_photo_url(car)
    return render_template("public/cars.html", cars=cars)

@app.route("/coche/<int:id>")
def car_detail(id):
    car = Car.query.get_or_404(id)
    if not car.activo and (not current_user.is_authenticated or not current_user.is_admin):
        abort(404)
    
    # Obtener URLs de todas las fotos
    car.photos_urls = [get_photo_url(car.id, photo.filename) for photo in car.fotos]
    car.primary_photo_url = get_primary_photo_url(car)
    
    return render_template("public/car_detail.html", car=car)

# Rutas de autenticación
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_raw = request.args.get('next')
            next_page = safe_redirect_target(next_raw) if next_raw else None
            flash('¡Inicio de sesión exitoso!', 'success')
            return redirect(next_page or url_for('admin_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    
    return render_template("login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('gestoria'))

# Rutas del admin
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    
    total_cars = Car.query.count()
    active_cars = Car.query.filter_by(activo=True).count()
    latest_cars = Car.query.order_by(Car.fecha_creacion.desc()).limit(5).all()
    
    # Añadir foto principal a los últimos coches
    for car in latest_cars:
        car.photo_url = get_primary_photo_url(car)
    
    return render_template("admin/dashboard.html", 
                         total_cars=total_cars,
                         active_cars=active_cars,
                         latest_cars=latest_cars)

@app.route("/admin/coches")
@login_required
def admin_cars():
    if not current_user.is_admin:
        abort(403)
    
    cars = Car.query.order_by(Car.fecha_creacion.desc()).all()
    # Añadir foto principal a cada coche
    for car in cars:
        car.photo_url = get_primary_photo_url(car)
    
    return render_template("admin/cars.html", cars=cars)


@app.route("/admin/cuenta", methods=['GET', 'POST'])
@login_required
def admin_account():
    if not current_user.is_admin:
        abort(403)

    user = User.query.get_or_404(current_user.id)
    pw_form = ChangePasswordForm(prefix='pw')
    username_form = ChangeUsernameForm(prefix='usr')
    email_form = ChangeEmailForm(prefix='em')

    if request.method == 'POST':
        form_id = request.form.get('form_id')

        if form_id == 'password':
            pw_form = ChangePasswordForm(prefix='pw', data=request.form)
            username_form = ChangeUsernameForm(prefix='usr')
            email_form = ChangeEmailForm(prefix='em')
            if user.email:
                email_form.email.data = user.email
            if pw_form.validate_on_submit():
                if not check_password_hash(user.password_hash, pw_form.current_password.data):
                    flash('La contraseña actual no es correcta.', 'danger')
                else:
                    user.password_hash = generate_password_hash(pw_form.new_password.data)
                    db.session.commit()
                    flash('Contraseña actualizada correctamente.', 'success')
                    return redirect(url_for('admin_account'))

        elif form_id == 'username':
            username_form = ChangeUsernameForm(prefix='usr', data=request.form)
            pw_form = ChangePasswordForm(prefix='pw')
            email_form = ChangeEmailForm(prefix='em')
            if user.email:
                email_form.email.data = user.email
            if username_form.validate_on_submit():
                if not check_password_hash(user.password_hash, username_form.current_password.data):
                    flash('La contraseña actual no es correcta.', 'danger')
                else:
                    new_u = (username_form.new_username.data or '').strip()
                    taken = User.query.filter(User.username == new_u, User.id != user.id).first()
                    if taken:
                        flash('Ese nombre de usuario ya está en uso.', 'danger')
                    elif new_u == user.username:
                        flash('El nuevo usuario es igual al actual.', 'warning')
                    else:
                        user.username = new_u
                        db.session.commit()
                        flash('Nombre de usuario actualizado. Usa el nuevo nombre para iniciar sesión.', 'success')
                        return redirect(url_for('admin_account'))

        elif form_id == 'email':
            email_form = ChangeEmailForm(prefix='em', data=request.form)
            pw_form = ChangePasswordForm(prefix='pw')
            username_form = ChangeUsernameForm(prefix='usr')
            if email_form.validate_on_submit():
                if not check_password_hash(user.password_hash, email_form.current_password.data):
                    flash('La contraseña actual no es correcta.', 'danger')
                else:
                    raw = (email_form.email.data or '').strip()
                    user.email = raw or None
                    db.session.commit()
                    flash('Correo guardado correctamente.', 'success')
                    return redirect(url_for('admin_account'))
    else:
        if user.email:
            email_form.email.data = user.email

    if not (request.method == 'POST' and request.form.get('form_id') == 'username'):
        username_form.new_username.data = user.username

    return render_template(
        'admin/account.html',
        user=user,
        pw_form=pw_form,
        username_form=username_form,
        email_form=email_form,
    )


@app.route("/admin/coche/nuevo", methods=['GET', 'POST'])
@login_required
def add_car():
    if not current_user.is_admin:
        abort(403)
    
    form = CarForm()
    if form.validate_on_submit():
        car = Car(
            marca=(form.marca.data or '').strip(),
            modelo=(form.modelo.data or '').strip(),
            año=form.año.data,
            precio=form.precio.data,
            kilometraje=form.kilometraje.data,
            tipo_combustible=form.tipo_combustible.data,
            descripcion=(form.descripcion.data or '').strip() or None,
        )
        db.session.add(car)
        db.session.flush()  # Obtener el ID sin commit
        
        # Guardar fotos si se subieron
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            save_car_photos(car.id, files)
        
        db.session.commit()
        flash('Coche añadido correctamente', 'success')
        return redirect(url_for('admin_cars'))
    
    return render_template("admin/add_car.html", form=form)

@app.route("/admin/coche/editar/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_car(id):
    if not current_user.is_admin:
        abort(403)

    car = Car.query.get_or_404(id)
    if request.method == 'POST':
        form = CarForm()
    else:
        form = CarForm(obj=car)

    if form.validate_on_submit():
        car.marca = (form.marca.data or '').strip()
        car.modelo = (form.modelo.data or '').strip()
        car.año = form.año.data
        car.precio = form.precio.data
        car.kilometraje = form.kilometraje.data
        car.tipo_combustible = form.tipo_combustible.data
        car.descripcion = (form.descripcion.data or '').strip() or None

        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            save_car_photos(car.id, files)

        db.session.commit()
        flash('Coche actualizado correctamente', 'success')
        return redirect(url_for('admin_cars'))

    car.existing_photos = [get_photo_url(car.id, photo.filename) for photo in car.fotos]

    return render_template("admin/edit_car.html", form=form, car=car)

@app.route("/admin/coche/eliminar-foto/<int:photo_id>", methods=['POST'])
@login_required
def delete_photo(photo_id):
    if not current_user.is_admin:
        abort(403)
    
    photo = CarPhoto.query.get_or_404(photo_id)
    car_id = photo.car_id
    was_primary = photo.is_primary

    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(car_id), photo.filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    except OSError:
        pass

    db.session.delete(photo)
    db.session.flush()

    if was_primary:
        next_photo = CarPhoto.query.filter_by(car_id=car_id).order_by(CarPhoto.orden.asc()).first()
        if next_photo:
            CarPhoto.query.filter_by(car_id=car_id).update({'is_primary': False})
            next_photo.is_primary = True

    db.session.commit()

    flash('Foto eliminada correctamente', 'success')
    return redirect(url_for('edit_car', id=car_id))

@app.route("/admin/coche/set-primary/<int:photo_id>", methods=['POST'])
@login_required
def set_primary_photo(photo_id):
    if not current_user.is_admin:
        abort(403)
    
    photo = CarPhoto.query.get_or_404(photo_id)
    car_id = photo.car_id
    
    # Quitar primary de todas las fotos del coche
    CarPhoto.query.filter_by(car_id=car_id).update({'is_primary': False})
    
    # Establecer esta foto como primary
    photo.is_primary = True
    db.session.commit()
    
    flash('Foto principal establecida', 'success')
    return redirect(url_for('edit_car', id=car_id))

@app.route("/admin/coche/eliminar/<int:id>", methods=['POST'])
@login_required
def delete_car(id):
    if not current_user.is_admin:
        abort(403)
    
    car = Car.query.get_or_404(id)
    car.activo = not car.activo
    db.session.commit()
    
    action = "activado" if car.activo else "desactivado"
    flash(f'Coche {action} correctamente', 'success')
    return redirect(url_for('admin_cars'))

@app.route("/admin/coche/borrar/<int:id>", methods=['POST'])
@login_required
def permanently_delete_car(id):
    if not current_user.is_admin:
        abort(403)
    
    car = Car.query.get_or_404(id)
    
    try:
        car_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
        if os.path.isdir(car_folder):
            for filename in os.listdir(car_folder):
                fp = os.path.join(car_folder, filename)
                if os.path.isfile(fp):
                    os.remove(fp)
            os.rmdir(car_folder)
    except OSError:
        pass
    
    # Eliminar de la base de datos (las fotos se eliminan por cascade)
    db.session.delete(car)
    db.session.commit()
    
    flash('Coche eliminado permanentemente', 'success')
    return redirect(url_for('admin_cars'))

# Manejo de errores
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500


@app.errorhandler(413)
def request_entity_too_large(e):
    flash('Los archivos superan el tamaño máximo permitido (16 MB en total por petición).', 'danger')
    return redirect(request.referrer or url_for('gestoria'))


# ============================================
# API REST - Para React Native / clientes externos
# ============================================
from flask_cors import CORS

CORS(app)

def car_to_dict(car):
    """Convierte un objeto Car a diccionario JSON"""
    primary_photo = next((p for p in car.fotos if p.is_primary), car.fotos[0] if car.fotos else None)
    return {
        'id': car.id,
        'marca': car.marca,
        'modelo': car.modelo,
        'año': car.año,
        'precio': car.precio,
        'kilometraje': car.kilometraje,
        'tipo_combustible': car.tipo_combustible,
        'descripcion': car.descripcion,
        'activo': car.activo,
        'fecha_creacion': car.fecha_creacion.isoformat() if car.fecha_creacion else None,
        'foto_principal': get_photo_url(car.id, primary_photo.filename) if primary_photo else None,
        'total_fotos': len(car.fotos)
    }

@app.route("/api/login", methods=['POST'])
def api_login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Faltan credenciales'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password_hash, data['password']):
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'is_admin': user.is_admin
            }
        })
    return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401

@app.route("/api/coches", methods=['GET'])
def api_coches():
    solo_activos = request.args.get('activos', 'true').lower() == 'true'
    query = Car.query
    if solo_activos:
        query = query.filter_by(activo=True)
    cars = query.order_by(Car.fecha_creacion.desc()).all()
    return jsonify([car_to_dict(car) for car in cars])

@app.route("/api/coche/<int:id>", methods=['GET'])
def api_coche_detalle(id):
    car = Car.query.get_or_404(id)
    data = car_to_dict(car)
    data['fotos'] = [get_photo_url(car.id, p.filename) for p in car.fotos]
    return jsonify(data)

@app.route("/api/dashboard", methods=['GET'])
def api_dashboard():
    return jsonify({
        'total_coches': Car.query.count(),
        'coches_activos': Car.query.filter_by(activo=True).count(),
        'coches_inactivos': Car.query.filter_by(activo=False).count(),
    })


@app.route("/api/coche/nuevo", methods=['POST'])
def api_nuevo_coche():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No se enviaron datos'}), 400
    car = Car(
        marca=data.get('marca'),
        modelo=data.get('modelo'),
        año=data.get('año'),
        precio=data.get('precio'),
        kilometraje=data.get('kilometraje', 0),
        tipo_combustible=data.get('tipo_combustible', 'gasolina'),
        descripcion=data.get('descripcion', '')
    )
    db.session.add(car)
    db.session.commit()
    return jsonify({'success': True, 'id': car.id})

@app.route("/api/coche/editar/<int:id>", methods=['PUT'])
def api_editar_coche(id):
    car = Car.query.get_or_404(id)
    data = request.get_json()
    car.marca = data.get('marca', car.marca)
    car.modelo = data.get('modelo', car.modelo)
    car.año = data.get('año', car.año)
    car.precio = data.get('precio', car.precio)
    car.kilometraje = data.get('kilometraje', car.kilometraje)
    car.tipo_combustible = data.get('tipo_combustible', car.tipo_combustible)
    car.descripcion = data.get('descripcion', car.descripcion)
    db.session.commit()
    return jsonify({'success': True})

@app.route("/api/coche/eliminar/<int:id>", methods=['DELETE'])
def api_eliminar_coche(id):
    car = Car.query.get_or_404(id)
    car.activo = not car.activo
    db.session.commit()
    return jsonify({'success': True, 'activo': car.activo})

@app.route("/api/coche/<int:id>/fotos", methods=['GET'])
def api_fotos_coche(id):
    car = Car.query.get_or_404(id)
    fotos = [{
        'id': p.id,
        'url': get_photo_url(car.id, p.filename),
        'is_primary': p.is_primary
    } for p in car.fotos]
    return jsonify(fotos)

@app.route("/api/coche/<int:id>/subir-foto", methods=['POST'])
def api_subir_foto(id):
    car = Car.query.get_or_404(id)
    if 'foto' not in request.files:
        return jsonify({'error': 'No se envió foto'}), 400
    file = request.files['foto']
    if file and allowed_file(file.filename):
        saved = save_car_photos(car.id, [file])
        if saved:
            return jsonify({'success': True})
    return jsonify({'error': 'Archivo no válido'}), 400


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_user_email_column()
        create_admin_user()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    _port = int(os.getenv('FLASK_PORT', '5000'))
    _host = os.getenv('FLASK_HOST', '127.0.0.1')
    app.run(debug=True, host=_host, port=_port)
