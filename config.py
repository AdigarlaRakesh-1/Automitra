import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Debug mode is explicitly environment-driven; disabled by default outside development
    _debug_env = os.environ.get('FLASK_DEBUG')
    if _debug_env is not None:
        DEBUG = _debug_env.lower() in ('true', '1', 'yes')
    else:
        DEBUG = (ENV == 'development')

    # In production, require an explicit SECRET_KEY
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if ENV == 'production':
            raise ValueError("CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable must be set in production mode!")
        SECRET_KEY = 'automitra-dev-fallback-secret-key-insecure'

    # Primary MySQL Connection (as suggested in project requirements)
    # Default format: mysql+pymysql://<user>:<password>@<host>:<port>/<dbname>
    MYSQL_USER = os.environ.get('MYSQL_USER')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'automitra')
    
    if MYSQL_USER and MYSQL_PASSWORD:
        MYSQL_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    else:
        MYSQL_URI = None
    
    # Can be overridden by DATABASE_URL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # SQLite fallback path
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLITE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'automitra.db')}"
    
    # Explicit SQLite toggle
    USE_SQLITE = os.environ.get('USE_SQLITE', 'false').lower() in ('true', '1', 'yes')

    # SQLAlchemy configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
