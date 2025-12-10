# src/routes/orders.py
from flask import Blueprint, render_template, request, redirect, session, url_for, current_app
from src.database import SessionLocal
from src.database.models import Pedido, DetallePedido, Producto, Notificacion
from datetime import datetime
import uuid
from src.extensions import socketio

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")

@orders_bp.route("/create", methods=["POST"])
def create_order():
    db = SessionLocal()
    user_id = session.get("user_id")

    # ejemplo: formulario envía listas producto_id[] y cantidad[]
    carrito = request.form.getlist("producto_id")
    cantidades = request.form.getlist("cantidad")

    total = 0
    detalles = []

    for prod_id, cant in zip(carrito, cantidades):
        producto = db.query(Producto).get(int(prod_id))
        precio = float(producto.precio) * int(cant)
        total += precio
        detalles.append({
            "id_producto": int(prod_id),
            "cantidad": int(cant),
            "precio_unitario": producto.precio
        })

    nuevo_pedido = Pedido(
        codigo_pedido=str(uuid.uuid4())[:8],
        id_usuario=user_id,
        total=total,
        estado="recibido"  # "recibido" indica que ya llegó al sistema
    )

    db.add(nuevo_pedido)
    db.commit()

    # Añadir detalles
    for d in detalles:
        detalle = DetallePedido(
            id_pedido=nuevo_pedido.id_pedido,
            id_producto=d["id_producto"],
            cantidad=d["cantidad"],
            precio_unitario=d["precio_unitario"]
        )
        db.add(detalle)

    # Notificación a admin (guardar en DB)
    # Nota: aquí asumo admin con id = 1; ideal: buscar todos los usuarios con rol admin
    noti_admin = Notificacion(
        id_usuario=1,
        tipo="nuevo_pedido",
        titulo="Nuevo pedido",
        mensaje=f"Nuevo pedido {nuevo_pedido.codigo_pedido}",
        id_pedido=nuevo_pedido.id_pedido
    )
    db.add(noti_admin)

    db.commit()

    # Emitir evento SocketIO para admin (namespace opcional '/notifications')
    payload = {
        "id_pedido": nuevo_pedido.id_pedido,
        "codigo_pedido": nuevo_pedido.codigo_pedido,
        "total": str(nuevo_pedido.total),
        "fecha_creacion": nuevo_pedido.fecha_creacion.isoformat()
    }
    # Emitir a todos (o a un room de admins si luego lo implementas)
    socketio.emit("new_order", payload, namespace="/notifications")

    return redirect(url_for("products.menu"))
