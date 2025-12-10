from flask import Blueprint, render_template
from src.database import SessionLocal
from src.database.models import Producto

products_bp = Blueprint("products", __name__)

@products_bp.route("/menu")
def menu():
    db = SessionLocal()
    productos = db.query(Producto).filter_by(disponible=True).all()
    return render_template("client/menu.html", productos=productos)
