from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template

from app.config import Config
from app.extensions import db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models  # noqa: F401
    from app.auth.routes import bp as auth_bp
    from app.genealogies.routes import bp as genealogies_bp
    from app.main.routes import bp as main_bp
    from app.members.routes import bp as members_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(genealogies_bp)
    app.register_blueprint(members_bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="页面不存在"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", code=500, message="服务器内部错误"), 500

    @app.cli.command("init-db")
    def init_db():
        with app.app_context():
            db.create_all()
        print("Database tables created.")

    return app
