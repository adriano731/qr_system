import pymysql
import pymysql.cursors

def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',       # Cambia si tienes contraseña
        db='registro_qr',  # Asegúrate de que esta base exista en phpMyAdmin
        port=3306,         # O 3308 si usas XAMPP y ese puerto
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
