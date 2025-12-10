# models.py
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, Boolean, 
    LargeBinary, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

Base = declarative_base()

class Rol(Base):
    __tablename__ = 'roles'
    id_rol = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False)

class Usuario(Base):
    __tablename__ = 'usuarios'
    id_usuario = Column(Integer, primary_key=True)
    nombre_usuario = Column(String(50), nullable=False, unique=True)
    contraseña_hash = Column(Text, nullable=False)
    telefono = Column(String(20), nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    activo = Column(Boolean, default=True)
    id_rol = Column(Integer, ForeignKey('roles.id_rol'), nullable=False)
    notificaciones_activas = Column(Boolean, default=True)
    
    rol = relationship('Rol', backref='usuarios')
    
    def set_password(self, password):
        self.contraseña_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.contraseña_hash, password)

class PerfilUsuario(Base):
    __tablename__ = 'perfiles_usuarios'
    id_perfil_usuario = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    apellidoP = Column(String(100), nullable=False)
    apellidoM = Column(String(100))
    email = Column(String(100), unique=True)
    colonia = Column(Text)
    calle = Column(Text)
    no_exterior = Column(Text)
    foto_perfil = Column(LargeBinary)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario'), unique=True)
    
    usuario = relationship('Usuario', backref='perfil')

class Producto(Base):
    __tablename__ = 'productos'
    id_producto = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text)
    precio = Column(Numeric(10, 2), nullable=False)
    imagen = Column(LargeBinary)
    disponible = Column(Boolean, default=True)
    tiempo_preparacion = Column(Integer)

class Pedido(Base):
    __tablename__ = 'pedidos'
    id_pedido = Column(Integer, primary_key=True)
    codigo_pedido = Column(String(20), nullable=False, unique=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario'), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    estado = Column(String(20), default='pendiente')
    notas = Column(Text)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cliente = relationship('Usuario', backref='pedidos')

class DetallePedido(Base):
    __tablename__ = 'detalles_pedido'
    id_detalle_pedido = Column(Integer, primary_key=True)
    id_pedido = Column(Integer, ForeignKey('pedidos.id_pedido'), nullable=False)
    id_producto = Column(Integer, ForeignKey('productos.id_producto'), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    nota = Column(Text)
    
    pedido = relationship('Pedido', backref='detalles')
    producto = relationship('Producto', backref='detalles')

class Notificacion(Base):
    __tablename__ = 'notificaciones'
    id_notificacion = Column(Integer, primary_key=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario'), nullable=False)
    tipo = Column(String(20), nullable=False)
    titulo = Column(String(100), nullable=False)
    mensaje = Column(Text, nullable=False)
    leida = Column(Boolean, default=False)
    id_pedido = Column(Integer, ForeignKey('pedidos.id_pedido'))
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    usuario = relationship('Usuario', backref='notificaciones')
    pedido = relationship('Pedido', backref='notificaciones')

class Conexion(Base):
    __tablename__ = 'conexiones'
    id_conexion = Column(Integer, primary_key=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario'), nullable=False)
    session_id = Column(String(255), nullable=False)
    tipo = Column(String(20), nullable=False)
    ultima_actividad = Column(DateTime, default=datetime.utcnow)
    
    usuario = relationship('Usuario', backref='conexiones')