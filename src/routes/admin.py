# src/routes/admin.py
from flask import Blueprint, render_template, redirect, request, url_for
from src.database import SessionLocal
from src.database.models import Pedido, Notificacion, Usuario
from src.extensions import socketio

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/dashboard")
def dashboard():
    db = SessionLocal()
    pedidos = db.query(Pedido).order_by(Pedido.fecha_creacion.desc()).all()
    return render_template("admin/dashboard.html", pedidos=pedidos)

@admin_bp.route("/pedido/<int:id>/estado", methods=["POST"])
def cambiar_estado(id):
    db = SessionLocal()
    pedido = db.query(Pedido).get(id)

    nuevo_estado = request.form.get("estado")
    pedido.estado = nuevo_estado

    # Notificar al cliente (guardar en DB)
    noti = Notificacion(
        id_usuario=pedido.id_usuario,
        tipo="cambio_estado",
        titulo="Actualización de tu pedido",
        mensaje=f"Tu pedido {pedido.codigo_pedido} ahora está: {nuevo_estado}",
        id_pedido=id
    )
    db.add(noti)
    db.commit()

    # Emitir evento al cliente conectado (podrías emitir a room = f"user_{pedido.id_usuario}")
    payload = {
        "id_pedido": pedido.id_pedido,
        "codigo_pedido": pedido.codigo_pedido,
        "nuevo_estado": nuevo_estado
    }
    # Emitir evento general; en el cliente filtras por id_pedido / user
    socketio.emit("order_update", payload, namespace="/notifications")

    return redirect(url_for("admin.dashboard"))
