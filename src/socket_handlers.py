# src/socket_handlers.py
from flask_socketio import emit, join_room, leave_room
from src.extensions import socketio
from flask import session, request
from src.database import SessionLocal
from src.database.models import Conexion
from datetime import datetime

@socketio.on("connect", namespace="/notifications")
def handle_connect():
    # request.sid es el id de sesión de socket
    sid = request.sid
    # Si el usuario tiene sesión HTTP, el client puede mandar su user_id después
    print("SocketIO: client connected", sid)
    emit("connected", {"sid": sid})

@socketio.on("register_user", namespace="/notifications")
def handle_register_user(data):
    """
    El cliente (JS) debería emitir 'register_user' con {"user_id": 5}
    para que el servidor lo ponga en un room: room f"user_{user_id}"
    """
    user_id = data.get("user_id")
    if not user_id:
        return
    room = f"user_{user_id}"
    join_room(room)
    print(f"SocketIO: join room {room}")

@socketio.on("disconnect", namespace="/notifications")
def handle_disconnect():
    print("SocketIO: client disconnected", request.sid)
