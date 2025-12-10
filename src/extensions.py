# src/extensions.py
from flask_socketio import SocketIO

# permitir CORS si el frontend está en el mismo dominio no es problema
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
