
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_FILE, override=False)

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-before-deployment")

    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "billsplit_campus")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))

    MYSQL_SSL_CA = os.getenv(
        "MYSQL_SSL_CA",
        os.path.join(BASE_DIR, "tidb-ca.pem")
    )
