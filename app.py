from flask import Flask, render_template, request, redirect, session  # ← activa lo que estaba comentado

import os
import qrcode
from datetime import datetime
from db_config import get_db_connection

app = Flask(__name__)
app.secret_key = 'clave_super_secreta'

# Crear carpetas si no existen
os.makedirs('static/qr', exist_ok=True)
os.makedirs('static/qr/vehiculos', exist_ok=True)
os.makedirs('static/qr/fotos_estudiantes', exist_ok=True)

# --- RUTA DE INICIO ---
@app.route('/')
def index():
    return render_template('login.html')

# --- LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contrasena = request.form['contraseña']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE usuario = %s AND contraseña = %s", (usuario, contrasena))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['usuario'] = user['usuario']
            session['rol'] = user['rol']
            return redirect('/dashboard')
        else:
            return "Credenciales inválidas. <a href='/'>Volver</a>"

    # Si es GET, muestra el formulario
    return render_template('login.html')

# --- DASHBOARD ---
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect('/')
    return render_template('deshboard.html', usuario=session['usuario'], rol=session['rol'])

# --- REGISTRO / ACTUALIZACIÓN DE ESTUDIANTE ---
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    conn = get_db_connection()
    cursor = conn.cursor()
    qr_path = None

    if request.method == 'POST':
        estudiante_id = int(request.form['id'])
        nombre = request.form['nombre']
        apellidos = request.form['apellidos']
        curso = request.form['curso']
        tiene_vehiculo = int(request.form.get('tiene_vehiculo', 0))
        accion = request.form['accion']

        if accion == 'registrar':
            cursor.execute("""
                INSERT INTO estudiantes (id, nombre, apellidos, curso, tiene_vehiculo)
                VALUES (%s, %s, %s, %s, %s)
            """, (estudiante_id, nombre, apellidos, curso, tiene_vehiculo))

        elif accion == 'actualizar':
            cursor.execute("""
                UPDATE estudiantes
                SET nombre = %s, apellidos = %s, curso = %s, tiene_vehiculo = %s
                WHERE id = %s
            """, (nombre, apellidos, curso, tiene_vehiculo, estudiante_id))

        # Guardar foto del estudiante
        if 'foto_estudiante' in request.files:
            foto_estudiante = request.files['foto_estudiante']
            if foto_estudiante and foto_estudiante.filename != '':
                foto_path = f"static/qr/fotos_estudiantes/{estudiante_id}.jpg"
                foto_estudiante.save(foto_path)

        # Guardar datos del vehículo
        if tiene_vehiculo:
            modelo = request.form['modelo']
            placa = request.form['placa']
            tipo = request.form['tipo']
            foto = request.files['foto']
            foto_path = f"static/qr/vehiculos/{placa}.jpg"
            if foto:
                foto.save(foto_path)

            cursor.execute("SELECT * FROM vehiculos WHERE estudiante_id = %s", (estudiante_id,))
            vehiculo_existente = cursor.fetchone()

            if vehiculo_existente:
                cursor.execute("""
                    UPDATE vehiculos SET modelo = %s, placa = %s, tipo = %s, foto = %s
                    WHERE estudiante_id = %s
                """, (modelo, placa, tipo, foto_path, estudiante_id))
            else:
                cursor.execute("""
                    INSERT INTO vehiculos (estudiante_id, modelo, placa, tipo, foto)
                    VALUES (%s, %s, %s, %s, %s)
                """, (estudiante_id, modelo, placa, tipo, foto_path))

        # Generar QR
        qr_data = f"http://192.168.100.73:5000/perfil/{estudiante_id}"
        qr_img = qrcode.make(qr_data)
        qr_path = f"qr/estudiante_{estudiante_id}.png"
        qr_img.save(f"static/{qr_path}")

        conn.commit()

    cursor.execute("SELECT * FROM estudiantes")
    estudiantes = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('registro.html', estudiantes=estudiantes, qr_path=qr_path)

# --- VER QR ---
@app.route('/ver_qr/<int:estudiante_id>')
def ver_qr(estudiante_id):
    qr_path = f"qr/estudiante_{estudiante_id}.png"
    return render_template('ver_qr.html', estudiante_id=estudiante_id, qr_path=qr_path)

# --- ELIMINAR ESTUDIANTE ---
@app.route('/eliminar_estudiante', methods=['POST'])
def eliminar_estudiante():
    estudiante_id = int(request.form['id'])
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM vehiculos WHERE estudiante_id = %s", (estudiante_id,))
    vehiculo = cursor.fetchone()

    # Eliminar QR
    qr_path = f"static/qr/estudiante_{estudiante_id}.png"
    if os.path.exists(qr_path):
        os.remove(qr_path)

    # Eliminar foto del vehículo
    if vehiculo and vehiculo[4] and os.path.exists(vehiculo[4]):
        os.remove(vehiculo[4])

    # Eliminar foto del estudiante
    foto_estudiante_path = f"static/qr/fotos_estudiantes/{estudiante_id}.jpg"
    if os.path.exists(foto_estudiante_path):
        os.remove(foto_estudiante_path)

    # Eliminar de la base de datos
    cursor.execute("DELETE FROM vehiculos WHERE estudiante_id = %s", (estudiante_id,))
    cursor.execute("DELETE FROM estudiantes WHERE id = %s", (estudiante_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/registro')

# --- PERFIL DEL ESTUDIANTE ---
@app.route('/perfil/<int:estudiante_id>')
def perfil(estudiante_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM estudiantes WHERE id = %s", (estudiante_id,))
    estudiante = cursor.fetchone()

    cursor.execute("SELECT * FROM vehiculos WHERE estudiante_id = %s", (estudiante_id,))
    vehiculo = cursor.fetchone()

    ahora = datetime.now()
    fecha = ahora.date()
    hora = ahora.time()

    cursor.execute("""
        INSERT INTO registros_ingreso (estudiante_id, fecha, hora, tipo_registro)
        VALUES (%s, %s, %s, 'entrada')
    """, (estudiante_id, fecha, hora))

    conn.commit()
    cursor.close()
    conn.close()

    return render_template('perfil.html', estudiante=estudiante, vehiculo=vehiculo)

# --- BUSCAR ESTUDIANTE PARA AUTOCOMPLETAR ---
@app.route('/buscar_estudiante/<int:estudiante_id>')
def buscar_estudiante(estudiante_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM estudiantes WHERE id = %s", (estudiante_id,))
    estudiante = cursor.fetchone()
    cursor.close()
    conn.close()

    if estudiante:
        return jsonify({
            "existe": True,
            "nombre": estudiante[1],
            "apellidos": estudiante[2],
            "curso": estudiante[3],
            "tiene_vehiculo": estudiante[4]
        })
    else:
        return jsonify({"existe": False})

# --- CERRAR SESIÓN ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- ESCANEAR QR ---
@app.route('/escanear')
def escanear():
    return render_template('escanear.html')


if __name__ == '__main__':
    app.run()
