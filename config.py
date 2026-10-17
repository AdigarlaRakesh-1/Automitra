import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'automitra-super-secret-key-2026')
    
    # Primary MySQL Connection (as suggested in project requirements)
    # Default format: mysql+pymysql://<user>:<password>@<host>:<port>/<dbname>
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root')
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'automitra')
    
    MYSQL_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    
    # Can be overridden by DATABASE_URL
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # SQLite fallback path
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLITE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'automitra.db')}"
    
    # SQLAlchemy configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
