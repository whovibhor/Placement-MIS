import mysql.connector
import config

conn = mysql.connector.connect(
    host=config.DB_HOST,
    port=config.DB_PORT,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    database=config.DB_NAME,
    charset="utf8mb4",
    collation="utf8mb4_general_ci",
)
c = conn.cursor()
c.execute("UPDATE students SET sr_no = NULL WHERE sr_no REGEXP '[^0-9]'")
conn.commit()
c.execute("ALTER TABLE students MODIFY COLUMN sr_no INT")
conn.commit()
c.close()
conn.close()
print("Done")
