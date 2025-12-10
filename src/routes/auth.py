from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from src.database import SessionLocal
from src.database.models import Usuario, Rol

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    db = SessionLocal()
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = db.query(Usuario).filter_by(nombre_usuario=username).first()

        if not user or not user.check_password(password):
            flash("Usuario o contraseña incorrectos")
            return redirect(url_for("auth.login"))

        session["user_id"] = user.id_usuario
        session["rol"] = user.rol.nombre

        if user.rol.nombre == "admin":
            return redirect(url_for("admin.dashboard"))

        return redirect(url_for("products.menu"))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    db = SessionLocal()

    if request.method == "POST":
        username = request.form.get("username")
        telefono = request.form.get("telefono")
        password = request.form.get("password")

        if db.query(Usuario).filter_by(nombre_usuario=username).first():
            flash("Ese usuario ya existe")
            return redirect(url_for("auth.register"))

        cliente_rol = db.query(Rol).filter_by(nombre="cliente").first()

        new_user = Usuario(
            nombre_usuario=username,
            telefono=telefono,
            id_rol=cliente_rol.id_rol
        )
        new_user.set_password(password)

        db.add(new_user)
        db.commit()

        flash("Registro exitoso")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")
