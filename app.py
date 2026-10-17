import os
import sys
from flask import Flask, render_template
from sqlalchemy import create_engine, text
from config import Config
from models import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # In testing mode, use in-memory database
    if app.config.get('TESTING'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///:memory:')
    else:
        # Determine database connection: MySQL with graceful SQLite fallback
        db_uri = app.config.get('DATABASE_URL') or app.config.get('MYSQL_URI')
        use_sqlite = os.environ.get('USE_SQLITE', 'false').lower() == 'true'
        
        if not use_sqlite and db_uri.startswith('mysql'):
            try:
                print(f"Connecting to MySQL: {app.config.get('MYSQL_HOST')}:{app.config.get('MYSQL_PORT')}...")
                test_engine = create_engine(db_uri, connect_args={'connect_timeout': 2})
                with test_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print("Successfully connected to MySQL database!")
                app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
            except Exception as e:
                print(f"Notice: MySQL connection not available ({e}).")
                print("Falling back to embedded SQLite database (automitra.db) for zero-setup execution.")
                app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLITE_URI']
        else:
            app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLITE_URI']

    db.init_app(app)

    # Register Jinja context & filters
    @app.template_filter('currency')
    def currency_filter(val):
        if val is None:
            return "₹0.00"
        try:
            return f"₹{float(val):,.2f}"
        except (ValueError, TypeError):
            return f"₹{val}"

    @app.template_filter('format_date')
    def format_date_filter(val, fmt='%b %d, %Y'):
        if val is None:
            return ""
        try:
            return val.strftime(fmt)
        except Exception:
            return str(val)

    # Register blueprints
    from routes.main import main_bp
    from routes.customers import customers_bp
    from routes.vehicles import vehicles_bp
    from routes.mechanics import mechanics_bp
    from routes.bookings import bookings_bp
    from routes.services import services_bp
    from routes.inventory import inventory_bp
    from routes.billing import billing_bp
    from routes.payments import payments_bp
    from routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(vehicles_bp)
    app.register_blueprint(mechanics_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html', error=str(e)), 500

    # Auto create tables and seed only if explicitly configured
    if app.config.get('AUTO_CREATE_TABLES'):
        with app.app_context():
            db.create_all()
            if app.config.get('AUTO_SEED'):
                from seed_data import seed_database
                seed_database()

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting AutoMitra Web Application on http://127.0.0.1:{port}")
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=port, debug=True)
