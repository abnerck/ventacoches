from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, TextAreaField, IntegerField, SelectField, SubmitField, FileField
from wtforms.validators import DataRequired, Length, NumberRange
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cars.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración para subida de imágenes
app.config['UPLOAD_FOLDER'] = 'static/uploads/cars'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB máximo
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# Función para verificar extensiones de archivo
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Modelos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

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

class CarForm(FlaskForm):
    marca = StringField('Marca', validators=[DataRequired(), Length(min=2, max=100)])
    modelo = StringField('Modelo', validators=[DataRequired(), Length(min=2, max=100)])
    año = IntegerField('Año', validators=[DataRequired(), NumberRange(min=1900, max=2024)])
    precio = FloatField('Precio (€)', validators=[DataRequired(), NumberRange(min=0)])
    kilometraje = IntegerField('Kilometraje (km)', validators=[NumberRange(min=0)])
    tipo_combustible = SelectField('Combustible', choices=[
        ('gasolina', 'Gasolina'),
        ('diesel', 'Diésel'),
        ('hibrido', 'Híbrido'),
        ('electrico', 'Eléctrico')
    ])
    descripcion = TextAreaField('Descripción')
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

# Función para guardar imágenes
def save_car_photos(car_id, files):
    saved_filenames = []
    
    for i, file in enumerate(files):
        if file and file.filename != '' and allowed_file(file.filename):
            # Generar nombre seguro único
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            original_name = secure_filename(file.filename)
            filename = f"{timestamp}_{original_name}"
            
            # Crear carpeta si no existe
            car_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(car_id))
            os.makedirs(car_folder, exist_ok=True)
            
            # Guardar archivo
            file_path = os.path.join(car_folder, filename)
            file.save(file_path)
            
            # Crear registro en la base de datos
            photo = CarPhoto(
                car_id=car_id,
                filename=filename,
                is_primary=(i == 0),  # La primera foto es la principal
                orden=i
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
def home():
    cars = Car.query.filter_by(activo=True).order_by(Car.fecha_creacion.desc()).limit(6).all()
    # Añadir URL de foto principal a cada coche
    for car in cars:
        car.photo_url = get_primary_photo_url(car)
    return render_template("index.html", cars=cars)

@app.route("/coches")
def public_cars():
    page = request.args.get('page', 1, type=int)
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
            next_page = request.args.get('next')
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
    return redirect(url_for('home'))

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

@app.route("/gestorianacional")
@login_required
def gestoria():
        
    return render_template("gestoria.html")   

@app.route("/admin/coche/nuevo", methods=['GET', 'POST'])
@login_required
def add_car():
    if not current_user.is_admin:
        abort(403)
    
    form = CarForm()
    if form.validate_on_submit():
        # Crear el coche primero
        car = Car(
            marca=form.marca.data,
            modelo=form.modelo.data,
            año=form.año.data,
            precio=form.precio.data,
            kilometraje=form.kilometraje.data,
            tipo_combustible=form.tipo_combustible.data,
            descripcion=form.descripcion.data
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
    form = CarForm(obj=car)
    
    if form.validate_on_submit():
        # Actualizar datos del coche
        car.marca = form.marca.data
        car.modelo = form.modelo.data
        car.año = form.año.data
        car.precio = form.precio.data
        car.kilometraje = form.kilometraje.data
        car.tipo_combustible = form.tipo_combustible.data
        car.descripcion = form.descripcion.data
        
        # Agregar nuevas fotos si se subieron
        if 'fotos' in request.files:
            files = request.files.getlist('fotos')
            save_car_photos(car.id, files)
        
        db.session.commit()
        flash('Coche actualizado correctamente', 'success')
        return redirect(url_for('admin_cars'))
    
    # Obtener URLs de las fotos existentes
    car.existing_photos = [get_photo_url(car.id, photo.filename) for photo in car.fotos]
    
    return render_template("admin/edit_car.html", form=form, car=car)

@app.route("/admin/coche/eliminar-foto/<int:photo_id>", methods=['POST'])
@login_required
def delete_photo(photo_id):
    if not current_user.is_admin:
        abort(403)
    
    photo = CarPhoto.query.get_or_404(photo_id)
    car_id = photo.car_id
    
    # Eliminar archivo físico
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(car_id), photo.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass
    
    # Eliminar registro de la base de datos
    db.session.delete(photo)
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
    
    # Eliminar fotos físicas
    try:
        car_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(id))
        if os.path.exists(car_folder):
            for filename in os.listdir(car_folder):
                file_path = os.path.join(car_folder, filename)
                os.remove(file_path)
            os.rmdir(car_folder)
    except:
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

# ============================================
# API REST - Para React Native
# ============================================
from flask_cors import CORS
from flask import jsonify
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
        create_admin_user()
        # Crear carpeta de uploads si no existe
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
