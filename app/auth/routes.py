from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import User


bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("genealogies.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("用户名、邮箱和密码不能为空。", "warning")
            return render_template("auth/register.html")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("用户名或邮箱已存在。", "danger")
            return render_template("auth/register.html")

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("注册成功，欢迎开始创建族谱。", "success")
        return redirect(url_for("genealogies.index"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("genealogies.index"))

    if request.method == "POST":
        account = request.form.get("account", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter((User.username == account) | (User.email == account.lower())).first()

        if user is None or not user.check_password(password):
            flash("账号或密码错误。", "danger")
            return render_template("auth/login.html")

        login_user(user)
        return redirect(url_for("genealogies.index"))

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录。", "info")
    return redirect(url_for("main.index"))
