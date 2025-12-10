from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, send_from_directory, abort
from functools import wraps
from sqlalchemy import func, text
from database import db_session 
from database.models import Rol, Usuario, Producto, Pedido, DetallePedido, Notificacion, PerfilUsuario
import os
import random
import string
import io
from datetime import datetime, date
from werkzeug.utils import secure_filename
import shutil
import re 
from decimal import Decimal
from itsdangerous import URLSafeTimedSerializer as Serializer 

# Directorio de imágenes por defecto
DEFAULT_IMAGE_PATH = os.path.join('static', 'images', 'default_profile.png')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sushi-secret-key-2024')
app.config['SESSION_COOKIE_SECURE'] = False

# Configuración para imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 5 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image(file):
    """Valida solo la extensión, la validación de tamaño se realiza en profile_edit."""
    if file and file.filename:
        if not allowed_file(file.filename):
            return False
        return True
    return False

# ----------------------------------------------------------------------
## 🔑 DECORADORES Y FUNCIONES AUXILIARES
# ----------------------------------------------------------------------

def get_usuario_actual():
    """Obtiene el usuario actual de la sesión (actualizado para SQLAlchemy 2.0)"""
    user_id = session.get('usuario_id')
    if user_id:
        # Usar Session.get() en lugar de Query.get()
        return db_session.get(Usuario, user_id)
    return None

def get_perfil_usuario_actual():
    """Obtiene el perfil del usuario actual"""
    usuario = get_usuario_actual()
    if usuario:
        return db_session.query(PerfilUsuario).filter_by(id_usuario=usuario.id_usuario).first()
    return None

def get_rol_usuario():
    """Obtiene el rol del usuario actual"""
    usuario = get_usuario_actual()
    if usuario and usuario.rol:
        return usuario.rol.nombre
    return None

def es_admin():
    """Verifica si el usuario es administrador"""
    return get_rol_usuario() == 'admin'

def requiere_login(f):
    """Decorador para requerir inicio de sesión"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_usuario_actual():
            flash('Por favor inicia sesión', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def requiere_admin(f):
    """Decorador para requerir rol de administrador"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not es_admin():
            flash('Acceso restringido a administradores', 'danger')
            return redirect(url_for('menu'))
        return f(*args, **kwargs)
    return decorated

# Funciones de TOKEN para Restablecimiento de Contraseña
def generate_reset_token(usuario):
    """Genera un token seguro para restablecer la contraseña."""
    s = Serializer(app.config['SECRET_KEY'], salt='password-reset-salt') 
    return s.dumps({'user_id': usuario.id_usuario})

def verify_reset_token(token, expires_sec=1800):
    """Verifica el token y retorna el objeto Usuario si es válido."""
    s = Serializer(app.config['SECRET_KEY'], salt='password-reset-salt')
    try:
        data = s.loads(token, max_age=expires_sec)
        user_id = data['user_id']
    except:
        return None
    # Usar Session.get() en lugar de Query.get()
    return db_session.get(Usuario, user_id)

def generar_codigo_pedido():
    """Genera un código único para el pedido (Ej: A7492)"""
    return f"{random.choice(string.ascii_uppercase)}{random.randint(1000, 9999)}"

# CONTEXT PROCESSOR
@app.context_processor
def inject_variables():
    """Inyecta variables en todas las plantillas"""
    usuario_actual = get_usuario_actual()
    perfil_actual = get_perfil_usuario_actual() 
    return dict(
        usuario_actual=usuario_actual,
        perfil_actual=perfil_actual, 
        es_admin_func=es_admin,
        datetime=datetime
    )

# ----------------------------------------------------------------------
## 🔐 RUTAS DE AUTENTICACIÓN Y PERFIL
# ----------------------------------------------------------------------

@app.route('/')
def index(): 
    usuario = get_usuario_actual()
    if usuario:
        return redirect(url_for('admin_dashboard' if es_admin() else 'menu'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = db_session.query(Usuario).filter_by(
            nombre_usuario=request.form['nombre_usuario']
        ).first()
        
        if usuario and usuario.check_password(request.form['contraseña']) and usuario.activo:
            session['usuario_id'] = usuario.id_usuario
            session['username'] = usuario.nombre_usuario
            session['role'] = usuario.rol.nombre if usuario.rol else 'cliente'
            
            if es_admin():
                flash(f'¡Bienvenido administrador {usuario.nombre_usuario}!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash(f'¡Bienvenido {usuario.nombre_usuario}!', 'success')
                return redirect(url_for('menu'))
        
        flash('Usuario o contraseña incorrectos', 'danger')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre_usuario = request.form.get('nombre_usuario', '').strip()
        contraseña = request.form.get('contraseña', '').strip()
        telefono = request.form.get('telefono', '').strip()
        
        if not all([nombre_usuario, contraseña, telefono]):
            flash('Todos los campos son obligatorios', 'danger')
            return render_template('auth/register.html')
        
        if len(contraseña) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'danger')
            return render_template('auth/register.html')
        
        if db_session.query(Usuario).filter_by(nombre_usuario=nombre_usuario).first():
            flash('El usuario ya existe', 'danger')
            return render_template('auth/register.html')
        
        rol_cliente = db_session.query(Rol).filter_by(nombre='cliente').first()
        if not rol_cliente:
            rol_cliente = Rol(nombre='cliente')
            db_session.add(rol_cliente)
            db_session.commit()
            rol_cliente = db_session.query(Rol).filter_by(nombre='cliente').first()
        
        try:
            nuevo_usuario = Usuario(
                nombre_usuario=nombre_usuario,
                telefono=telefono,
                id_rol=rol_cliente.id_rol,
                activo=True
            )
            nuevo_usuario.set_password(contraseña)
            
            db_session.add(nuevo_usuario)
            db_session.flush()
            
            perfil = PerfilUsuario(
                nombre="",
                apellidoP="",
                apellidoM="",
                id_usuario=nuevo_usuario.id_usuario
            )
            db_session.add(perfil)
            
            db_session.commit()
            flash('Registro exitoso. Inicia sesión.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db_session.rollback()
            flash(f'Error en el registro: {str(e)}', 'danger')
    
    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

# --- FIN RUTAS DE RECUPERACIÓN DE CONTRASEÑA ---

@app.route('/profile')
@requiere_login
def profile():
    usuario_actual = get_usuario_actual()
    perfil = get_perfil_usuario_actual()
    return render_template('client/profile.html', 
                            usuario=usuario_actual,
                            perfil=perfil)

@app.route('/profile/edit', methods=['GET', 'POST'])
@requiere_login
def profile_edit():
    usuario_actual = get_usuario_actual()
    perfil = get_perfil_usuario_actual()
    
    if request.method == 'POST':
        try:
            telefono = request.form.get('telefono')
            if telefono:
                usuario_actual.telefono = telefono
            
            if perfil:
                perfil.nombre = request.form.get('nombre', perfil.nombre)
                perfil.apellidoP = request.form.get('apellidoP', perfil.apellidoP)
                perfil.apellidoM = request.form.get('apellidoM', perfil.apellidoM)
                perfil.email = request.form.get('email', perfil.email)
                perfil.colonia = request.form.get('colonia', perfil.colonia)
                perfil.calle = request.form.get('calle', perfil.calle)
                perfil.no_exterior = request.form.get('no_exterior', perfil.no_exterior)
                
                if 'foto_perfil' in request.files:
                    imagen = request.files['foto_perfil']
                    if imagen.filename and allowed_file(imagen.filename):
                        imagen.seek(0, os.SEEK_END)
                        file_size = imagen.tell()
                        imagen.seek(0)
                        
                        if file_size > MAX_FILE_SIZE:
                            flash('La imagen es demasiado grande (máximo 5MB)', 'danger')
                        else:
                            perfil.foto_perfil = imagen.read() 
                
            db_session.commit()
            flash('Perfil actualizado correctamente', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            db_session.rollback()
            flash(f'Error al actualizar perfil: {str(e)}', 'danger')
    
    return render_template('client/profile_edit.html', 
                            usuario=usuario_actual, 
                            perfil=perfil)

@app.route('/profile/delete_picture', methods=['POST'])
@requiere_login
def delete_profile_picture():
    perfil = get_perfil_usuario_actual()
    if perfil:
        perfil.foto_perfil = None
        db_session.commit()
        flash('Foto de perfil eliminada', 'success')
    return redirect(url_for('profile'))

@app.route('/profile_picture/<int:usuario_id>')
def profile_picture(usuario_id):
    perfil = db_session.query(PerfilUsuario).filter_by(id_usuario=usuario_id).first()
    
    if perfil and perfil.foto_perfil:
        return send_file(
            io.BytesIO(perfil.foto_perfil),
            mimetype='image/jpeg', 
            as_attachment=False
        )
    
    try:
        image_directory = os.path.join(app.root_path, 'static', 'images')
        return send_from_directory(
            image_directory, 
            'default_profile.png'
        )
    except Exception:
        abort(404)

# ----------------------------------------------------------------------
## 🍽️ RUTAS DEL CLIENTE
# ----------------------------------------------------------------------

@app.route('/menu')
@requiere_login
def menu():
    # Si es admin, mostrar menú pero con indicador
    productos = db_session.query(Producto).filter_by(disponible=True).all()
    
    # Agregar un mensaje flash si es admin
    if es_admin():
        flash('🔧 Estás viendo el menú en modo administrador. Puedes regresar al panel en cualquier momento.', 'info')
    
    return render_template('client/menu.html', productos=productos)

# O crear una ruta separada para admin
@app.route('/admin/menu_preview')
@requiere_login
@requiere_admin
def admin_menu_preview():
    """Vista previa del menú para administradores"""
    productos = db_session.query(Producto).filter_by(disponible=True).all()
    return render_template('client/menu.html', 
                          productos=productos, 
                          es_admin=True,
                          mostrar_boton_admin=True)

@app.route('/carrito')
@requiere_login
def carrito():
    """Página del carrito de compras"""
    # ELIMINA esta condición:
    # if es_admin():
    #     return redirect(url_for('admin_dashboard'))
    
    return render_template('client/carrito.html')

@app.route('/orders')
@requiere_login
def orders():
    """Página de checkout/confirmación de pedido"""
    # ELIMINA esta condición:
    # if es_admin():
    #     return redirect(url_for('admin_dashboard'))
    
    usuario = get_usuario_actual()
    perfil = get_perfil_usuario_actual()
    
    return render_template('client/orders.html')

@app.route('/mis_pedidos')
@requiere_login
def mis_pedidos():
    # ELIMINA esta condición:
    # if es_admin():
    #     return redirect(url_for('admin_dashboard'))
    
    usuario = get_usuario_actual()
    pedidos = db_session.query(Pedido).filter_by(id_usuario=usuario.id_usuario)\
                             .order_by(Pedido.fecha_creacion.desc()).all()
    return render_template('client/view_orders.html', pedidos=pedidos)

@app.route('/debug_pedidos')
@requiere_login
def debug_pedidos():
    """Ruta para debug - ver pedidos del usuario actual"""
    usuario = get_usuario_actual()
    pedidos = db_session.query(Pedido).filter_by(id_usuario=usuario.id_usuario).all()
    
    resultado = []
    for p in pedidos:
        resultado.append({
            'id': p.id_pedido,
            'codigo': p.codigo_pedido,
            'estado': p.estado,
            'total': float(p.total),
            'detalles_count': len(p.detalles) if p.detalles else 0
        })
    
    return jsonify({
        'usuario_id': usuario.id_usuario,
        'usuario_nombre': usuario.nombre_usuario,
        'total_pedidos': len(pedidos),
        'pedidos': resultado
    })

@app.route('/order_details/<int:pedido_id>')
@requiere_login
def order_details(pedido_id):
    # if es_admin():
    #     return redirect(url_for('admin_dashboard'))
    
    usuario = get_usuario_actual()
    pedido = db_session.query(Pedido).filter(
        Pedido.id_pedido == pedido_id,
        Pedido.id_usuario == usuario.id_usuario
    ).first()

    if not pedido:
        flash('Pedido no encontrado o no te pertenece.', 'danger')
        return redirect(url_for('mis_pedidos'))

    subtotal_pedido = Decimal('0.00')
    for detalle in pedido.detalles:
        subtotal_pedido += Decimal(str(detalle.cantidad)) * Decimal(str(detalle.precio_unitario))
    
    return render_template('client/order_details.html', pedido=pedido, subtotal_pedido=subtotal_pedido)

@app.route('/generar_pedido', methods=['POST'])
@requiere_login
def generar_pedido():
    usuario = get_usuario_actual()
    
    try:
        form_data = request.form
        
        nombre = form_data.get('nombre')
        telefono = form_data.get('telefono')
        colonia = form_data.get('colonia')
        calle = form_data.get('calle')
        no_exterior = form_data.get('no_exterior')
        notas = form_data.get('notas')
        
        if not all([nombre, telefono, colonia, calle, no_exterior]):
            flash('Faltan datos obligatorios para generar el pedido.', 'danger')
            return redirect(url_for('orders'))
        
        items_pedido = []
        subtotal_pedido = Decimal('0.00')
        
        items_map = {}
        for key, value in form_data.items():
            match = re.search(r'items\[(\d+)\]\[(cantidad|precio)\]', key)
            if match:
                product_id = int(match.group(1))
                field = match.group(2)
                
                if product_id not in items_map:
                    items_map[product_id] = {'id': product_id, 'cantidad': 0, 'precio_unitario': Decimal('0.00')}
                    
                if field == 'cantidad':
                    try:
                        items_map[product_id]['cantidad'] = int(value)
                    except ValueError:
                        items_map[product_id]['cantidad'] = 0
                elif field == 'precio':
                    try:
                        items_map[product_id]['precio_unitario'] = Decimal(str(value))
                    except:
                        items_map[product_id]['precio_unitario'] = Decimal('0.00')

        items_pedido = [item for item in items_map.values() if item['cantidad'] > 0]

        if not items_pedido:
            flash('El carrito está vacío. Agrega productos para generar un pedido.', 'danger')
            return redirect(url_for('carrito'))

        for item in items_pedido:
            subtotal = Decimal(str(item['cantidad'])) * item['precio_unitario']
            subtotal_pedido += subtotal
            
        if subtotal_pedido <= Decimal('0.00'):
            flash('El total del pedido debe ser mayor a cero.', 'danger')
            return redirect(url_for('carrito'))
            
        total_con_impuestos = subtotal_pedido * Decimal('1.12')
            
        nuevo_pedido = Pedido(
            codigo_pedido=generar_codigo_pedido(), 
            id_usuario=usuario.id_usuario,
            total=total_con_impuestos,
            estado='pendiente', 
            notas=f"Cliente: {nombre}, Tel: {telefono}. Dirección: C. {calle} No. {no_exterior}, Col. {colonia}. Notas: {notas if notas else 'Ninguna.'}"
        )
        db_session.add(nuevo_pedido)
        db_session.flush()

        for item in items_pedido:
            detalle = DetallePedido(
                id_pedido=nuevo_pedido.id_pedido,
                id_producto=item['id'],
                cantidad=item['cantidad'],
                precio_unitario=item['precio_unitario']
            )
            db_session.add(detalle)
            
        perfil = get_perfil_usuario_actual()
        if perfil:
            if nombre and ' ' in nombre:
                partes_nombre = nombre.split(' ', 1)
                perfil.nombre = partes_nombre[0]
                if len(partes_nombre) > 1:
                    perfil.apellidoP = partes_nombre[1]
            
            usuario.telefono = telefono
            
            perfil.colonia = colonia
            perfil.calle = calle
            perfil.no_exterior = no_exterior

        db_session.commit()
        
        flash(f'¡Pedido #{nuevo_pedido.codigo_pedido} generado con éxito! Total: ${total_con_impuestos:.2f} (incluye impuestos)', 'success')
        
        return redirect(url_for('order_details', pedido_id=nuevo_pedido.id_pedido))

    except Exception as e:
        db_session.rollback()
        flash(f'Error al generar el pedido: {str(e)}', 'danger')
        return redirect(url_for('orders'))

# ----------------------------------------------------------------------
## 🖼️ RUTAS DE IMAGEN BINARIA
# ----------------------------------------------------------------------

@app.route('/product_image/<int:product_id>')
def product_image(product_id):
    producto = db_session.query(Producto).get(product_id)
    
    if producto and producto.imagen:
        return send_file(
            io.BytesIO(producto.imagen),
            mimetype='image/jpeg', 
            as_attachment=False
        )
    
    try:
        image_directory = os.path.join(app.root_path, 'static', 'images')
        return send_from_directory(
            image_directory, 
            'default_product.png'
        )
    except Exception:
        abort(404)

# ----------------------------------------------------------------------
## ⚙️ RUTAS DE ADMINISTRACIÓN
# ----------------------------------------------------------------------

@app.route('/admin')
@requiere_login
@requiere_admin
def admin_dashboard():
    hoy = date.today()
    
    stats = {
        'total_pedidos': db_session.query(Pedido).count(),
        'pedidos_hoy': db_session.query(Pedido).filter(
            func.date(Pedido.fecha_creacion) == hoy
        ).count(),
        'pedidos_pendientes': db_session.query(Pedido).filter_by(estado='pendiente').count(),
        'total_usuarios': db_session.query(Usuario).filter_by(activo=True).count(),
        'total_productos': db_session.query(Producto).filter_by(disponible=True).count()
    }
    
    pedidos_recientes = db_session.query(Pedido).order_by(
        Pedido.fecha_creacion.desc()
    ).limit(5).all()
    
    nuevos_usuarios = db_session.query(Usuario).order_by(
        Usuario.fecha_registro.desc()
    ).limit(5).all()
    
    return render_template('admin/dashboard.html',
                            stats=stats,
                            pedidos_recientes=pedidos_recientes,
                            nuevos_usuarios=nuevos_usuarios)

@app.route('/admin/view_profile/<int:usuario_id>')
@requiere_login
@requiere_admin
def view_profile(usuario_id):
    usuario = db_session.get(Usuario, usuario_id)
    if not usuario:
        flash('Usuario no encontrado', 'danger')
        return redirect(url_for('admin_users'))
    
    perfil = db_session.query(PerfilUsuario).filter_by(id_usuario=usuario_id).first()
    
    return render_template('admin/view_profile.html', 
                            usuario=usuario,
                            perfil=perfil)

# --- INICIO RUTAS CRUD PRODUCTOS ---

@app.route('/admin/products', methods=['GET', 'POST'])
@requiere_login
@requiere_admin
def admin_products():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        tiempo = request.form.get('tiempo_preparacion')
        imagen = request.files.get('imagen_producto')
        
        if not all([nombre, descripcion, precio, tiempo]):
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('admin_products'))
            
        try:
            precio_float = Decimal(precio)
            tiempo_int = int(tiempo)
            if precio_float <= 0 or tiempo_int <= 0:
                 raise ValueError("El precio y el tiempo deben ser positivos.")
        except ValueError:
            flash('Precio y Tiempo de preparación deben ser números válidos y positivos.', 'danger')
            return redirect(url_for('admin_products'))

        imagen_data = None
        if imagen and imagen.filename and allowed_file(imagen.filename):
            try:
                imagen_data = imagen.read()
            except Exception as e:
                flash(f'Error al leer la imagen: {str(e)}', 'warning')
                
        try:
            nuevo_producto = Producto(
                nombre=nombre,
                descripcion=descripcion,
                precio=precio_float,
                tiempo_preparacion=tiempo_int,
                imagen=imagen_data, 
                disponible=True
            )
            
            db_session.add(nuevo_producto)
            db_session.commit()
            flash(f'Producto "{nombre}" agregado con éxito.', 'success')
        except Exception as e:
            db_session.rollback()
            flash(f"Error de base de datos al agregar producto: {str(e)}", 'danger')
        
        return redirect(url_for('admin_products'))

    productos = db_session.query(Producto).order_by(Producto.nombre).all()
    return render_template('admin/products.html', productos=productos)

@app.route('/admin/api/edit_product/<int:product_id>', methods=['POST'])
@requiere_login
@requiere_admin
def edit_product(product_id):
    producto = db_session.query(Producto).get(product_id)
    if not producto:
        flash('Producto no encontrado', 'danger')
        return redirect(url_for('admin_products'))
    
    try:
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        tiempo = request.form.get('tiempo_preparacion')
        imagen = request.files.get('imagen_producto_edit')
        
        precio_decimal = Decimal(precio)
        tiempo_int = int(tiempo)

        producto.nombre = nombre
        producto.descripcion = descripcion
        producto.precio = precio_decimal
        producto.tiempo_preparacion = tiempo_int
        
        if imagen and imagen.filename and allowed_file(imagen.filename):
            producto.imagen = imagen.read()
        
        db_session.commit()
        flash(f'Producto "{producto.nombre}" actualizado con éxito.', 'success')
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al actualizar producto: {str(e)}', 'danger')
        
    return redirect(url_for('admin_products'))

# --- FIN RUTAS CRUD PRODUCTOS ---

@app.route('/admin/orders')
@requiere_login
@requiere_admin
def admin_orders():
    pedidos = db_session.query(Pedido).order_by(Pedido.fecha_creacion.desc()).all()
    return render_template('admin/orders.html', pedidos=pedidos)

@app.route('/admin/users')
@requiere_login
@requiere_admin
def admin_users():
    usuarios = db_session.query(Usuario).join(Rol).order_by(Usuario.fecha_registro.desc()).all()
    return render_template('admin/users.html', usuarios=usuarios)

# ----------------------------------------------------------------------
## 📲 APIs para AJAX
# ----------------------------------------------------------------------

@app.route('/admin/api/order_details/<int:pedido_id>')
@requiere_login
@requiere_admin
def api_order_details(pedido_id):
    # Usar Session.get() en lugar de Query.get()
    pedido = db_session.get(Pedido, pedido_id)
    if not pedido:
        return jsonify({'error': 'Pedido no encontrado'}), 404
    
    detalles = []
    for detalle in pedido.detalles:
        detalles.append({
            'producto': detalle.producto.nombre,
            'cantidad': detalle.cantidad,
            'precio': float(detalle.precio_unitario), 
            'subtotal': float(detalle.cantidad * detalle.precio_unitario)
        })
    
    return jsonify({
        'pedido_id': pedido.id_pedido,
        'codigo': pedido.codigo_pedido,
        'cliente': pedido.cliente.nombre_usuario,
        'total': float(pedido.total),
        'estado': pedido.estado,
        'notas': pedido.notas or 'Sin notas',
        'fecha': pedido.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'detalles': detalles
    })

@app.route('/admin/api/change_order_status', methods=['POST'])
@requiere_login
@requiere_admin
def change_order_status():
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    
    # Usar Session.get() en lugar de Query.get()
    pedido = db_session.get(Pedido, order_id)
    if pedido and new_status:
        pedido.estado = new_status
        db_session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Pedido no encontrado'})

@app.route('/admin/api/toggle_product_status', methods=['POST'])
@requiere_login
@requiere_admin
def toggle_product_status():
    data = request.get_json(silent=True) or request.form
    product_id = data.get('product_id') or request.args.get('product_id')
    
    # Usar Session.get() en lugar de Query.get()
    producto = db_session.get(Producto, product_id)
    if producto:
        producto.disponible = not producto.disponible
        db_session.commit()
        return jsonify({'success': True, 'disponible': producto.disponible})
    
    return jsonify({'success': False, 'error': 'Producto no encontrado'})

@app.route('/admin/api/toggle_user_status', methods=['POST'])
@requiere_login
@requiere_admin
def toggle_user_status():
    user_id = request.form.get('user_id')
    
    # Usar Session.get() en lugar de Query.get()
    usuario = db_session.get(Usuario, user_id)
    if usuario:
        usuario.activo = not usuario.activo
        db_session.commit()
        return jsonify({'success': True, 'activo': usuario.activo})
    
    return jsonify({'success': False, 'error': 'Usuario no encontrado'})

# --- APIs CRUD PRODUCTOS ---

@app.route('/admin/api/delete_product/<int:product_id>', methods=['DELETE'])
@requiere_login
@requiere_admin
def delete_product(product_id):
    # Usar Session.get() en lugar de Query.get()
    producto = db_session.get(Producto, product_id)
    if not producto:
        return jsonify({'success': False, 'message': 'Producto no encontrado'}), 404
        
    try:
        db_session.delete(producto)
        db_session.commit()
        return jsonify({'success': True, 'message': 'Producto eliminado correctamente'})
        
    except Exception as e:
        db_session.rollback()
        return jsonify({'success': False, 'message': f'Error al eliminar el producto: {str(e)}'}), 500

@app.route('/admin/api/get_product/<int:product_id>', methods=['GET'])
@requiere_login
@requiere_admin
def get_product(product_id):
    # Usar Session.get() en lugar de Query.get()
    producto = db_session.get(Producto, product_id)
    if not producto:
        return jsonify({'success': False, 'message': 'Producto no encontrado'}), 404
    
    has_image = producto.imagen is not None
    
    return jsonify({
        'success': True,
        'id': producto.id_producto,
        'nombre': producto.nombre,
        'descripcion': producto.descripcion,
        'precio': float(producto.precio),
        'tiempo_preparacion': producto.tiempo_preparacion,
        'has_image': has_image, 
        'disponible': producto.disponible
    })

# ----------------------------------------------------------------------
## 🔄 API PARA AGREGAR AL CARRITO DESDE EL MENÚ
# ----------------------------------------------------------------------

@app.route('/api/agregar_al_carrito', methods=['POST'])
@requiere_login
def agregar_al_carrito():
    """API para agregar productos al carrito (usada desde el menú)"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        nombre = data.get('nombre')
        precio = data.get('precio')
        
        if not all([product_id, nombre, precio]):
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400
        
        return jsonify({
            'success': True,
            'message': f'{nombre} agregado al carrito',
            'producto': {
                'id': int(product_id),
                'nombre': nombre,
                'precio': float(precio),
                'cantidad': 1
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    

def inicializar_roles():
    """Crea los roles básicos si no existen"""
    roles_necesarios = ['cliente', 'admin']
    
    for rol_nombre in roles_necesarios:
        rol_existente = db_session.query(Rol).filter_by(nombre=rol_nombre).first()
        if not rol_existente:
            nuevo_rol = Rol(nombre=rol_nombre)
            db_session.add(nuevo_rol)
            print(f"Rol '{rol_nombre}' creado")
    
    try:
        db_session.commit()
        print("Roles inicializados correctamente")
    except Exception as e:
        db_session.rollback()
        print(f"Error al crear roles: {e}")

if __name__ == '__main__':
    # Inicializar roles antes de correr la app
    with app.app_context():
        inicializar_roles()

# ----------------------------------------------------------------------
## 🧹 CIERRE DE SESIÓN PARA EVITAR TIMEOUTERROR
# ----------------------------------------------------------------------

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Remueve la sesión de la base de datos después de cada petición."""
    db_session.remove() 

# ----------------------------------------------------------------------
## 🚀 INICIO DE LA APLICACIÓN
# ----------------------------------------------------------------------

if __name__ == '__main__':
    os.makedirs(os.path.join('static', 'images'), exist_ok=True)
    app.run(debug=True, port=5000)