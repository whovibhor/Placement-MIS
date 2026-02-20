import os

# ============================================================
#  DATABASE CONFIGURATION — UPDATE THESE WITH YOUR CREDENTIALS
# ============================================================
DB_HOST = "localhost"
DB_PORT = 3307
DB_USER = "root"                # <-- your MySQL username
DB_PASSWORD = "admin"   # <-- your MySQL password
DB_NAME = "placementmis"       # <-- database name (will be created automatically)

# Flask
SECRET_KEY = os.urandom(24)
