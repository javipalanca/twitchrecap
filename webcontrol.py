import os
import signal
import subprocess
import psutil
import json
import secrets
import datetime
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from signal_handlers import send_reset_memory_signal
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Genera una clave secreta aleatoria

# Configuración de registro de depuración
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

def debug_log(message):
    """Función centralizada para registrar mensajes de depuración"""
    if DEBUG:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DEBUG] {timestamp} - {message}")

# Configuración de autenticación
# Leer credenciales desde el archivo .env
USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
PASSWORD = os.getenv('ADMIN_PASSWORD', 'contraseña_segura')

debug_log(f"Credenciales cargadas - Usuario: {USERNAME}, Contraseña configurada: {'Sí' if PASSWORD else 'No'}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Variables globales para guardar los procesos de los bots
bot_process = None
discord_bot_process = None

# Función para obtener los PIDs de los procesos de los bots
def get_bot_pids():
    twitch_pid = None
    discord_pid = None
    
    debug_log("Iniciando búsqueda de PIDs de bots")
    
    # Primero intentar leer los archivos PID si existen
    try:
        if os.path.exists('twitch_bot.pid'):
            with open('twitch_bot.pid', 'r') as f:
                twitch_pid = int(f.read().strip())
            debug_log(f"Archivo twitch_bot.pid encontrado, PID: {twitch_pid}")
            # Verificar que el proceso existe
            try:
                os.kill(twitch_pid, 0)  # Señal 0 solo verifica que el proceso existe
                debug_log(f"Proceso Twitch con PID {twitch_pid} existe")
            except OSError as e:
                debug_log(f"Proceso Twitch con PID {twitch_pid} no existe: {e}")
                twitch_pid = None  # El proceso no existe
    except Exception as e:
        debug_log(f"Error al leer archivo twitch_bot.pid: {e}")
        
    try:
        if os.path.exists('discord_bot.pid'):
            with open('discord_bot.pid', 'r') as f:
                discord_pid = int(f.read().strip())
            debug_log(f"Archivo discord_bot.pid encontrado, PID: {discord_pid}")
            # Verificar que el proceso existe
            try:
                os.kill(discord_pid, 0)  # Señal 0 solo verifica que el proceso existe
                debug_log(f"Proceso Discord con PID {discord_pid} existe")
            except OSError as e:
                debug_log(f"Proceso Discord con PID {discord_pid} no existe: {e}")
                discord_pid = None  # El proceso no existe
    except Exception as e:
        debug_log(f"Error al leer archivo discord_bot.pid: {e}")
    
    # Si no se encontraron PIDs en los archivos, buscar en los procesos
    if not twitch_pid or not discord_pid:
        debug_log("Buscando PIDs a través de psutil ya que no se encontraron en archivos o no son válidos")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and len(cmdline) > 1 and 'python' in cmdline[0]:
                    # Verificar el nombre exacto del script y la ruta completa si está disponible
                    script_name = os.path.basename(cmdline[1]) if len(cmdline) > 1 else ""
                    
                    if script_name == 'bot.py':
                        if not twitch_pid:  # Solo asignar si aún no se encontró
                            twitch_pid = proc.info['pid']
                            debug_log(f"Proceso Twitch encontrado mediante psutil, PID: {twitch_pid}, Comando: {cmdline}")
                    elif script_name == 'discordbot.py':
                        if not discord_pid:  # Solo asignar si aún no se encontró
                            discord_pid = proc.info['pid']
                            debug_log(f"Proceso Discord encontrado mediante psutil, PID: {discord_pid}, Comando: {cmdline}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                debug_log(f"Error al inspeccionar proceso con psutil: {e}")
    
    debug_log(f"Búsqueda de PIDs completada - Twitch PID: {twitch_pid}, Discord PID: {discord_pid}")
    return twitch_pid, discord_pid

# Referencia a los procesos de los bots para acceder a sus objetos
twitch_bot_instance = None
discord_bot_instance = None

@app.route('/')
@login_required
def index():
    debug_log("Acceso a la página principal")
    twitch_pid, discord_pid = get_bot_pids()
    twitch_status = "En ejecución" if twitch_pid else "Detenido"
    discord_status = "En ejecución" if discord_pid else "Detenido"
    
    debug_log(f"Estado actual de los bots - Twitch: {twitch_status} (PID: {twitch_pid}), Discord: {discord_status} (PID: {discord_pid})")
    
    return render_template('index.html', 
                          twitch_status=twitch_status, 
                          discord_status=discord_status)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    debug_log("Acceso a la página de login")
    
    if request.method == 'POST':
        entered_username = request.form['username']
        entered_password = request.form['password']
        debug_log(f"Intento de login - Usuario ingresado: {entered_username}")
        
        if entered_username == USERNAME and entered_password == PASSWORD:
            debug_log(f"Autenticación exitosa para el usuario: {entered_username}")
            session['logged_in'] = True
            flash('Has iniciado sesión correctamente')
            next_url = request.args.get('next') or url_for('index')
            debug_log(f"Redirigiendo a: {next_url}")
            return redirect(next_url)
        else:
            error = 'Credenciales inválidas. Por favor, inténtalo de nuevo.'
            debug_log(f"Error de autenticación - Usuario coincide: {entered_username == USERNAME}, Contraseña coincide: {entered_password == PASSWORD}")
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    if 'logged_in' in session:
        debug_log("Usuario cerró sesión")
    session.pop('logged_in', None)
    flash('Has cerrado sesión')
    return redirect(url_for('login'))

@app.route('/start_twitch_bot')
@login_required
def start_twitch_bot():
    global bot_process
    
    debug_log("Iniciando proceso de arranque del bot de Twitch")
    
    # Verificar si el bot ya está en ejecución
    twitch_pid, _ = get_bot_pids()
    if twitch_pid:
        debug_log(f"El bot de Twitch ya está en ejecución con PID {twitch_pid}, cancelando arranque")
        return jsonify({"status": "error", "message": "El bot de Twitch ya está en ejecución"})
    
    # Iniciar el bot de Twitch
    try:
        debug_log("Intentando iniciar proceso del bot de Twitch")
        bot_process = subprocess.Popen(['python', 'bot.py'])
        debug_log(f"Bot de Twitch iniciado correctamente con PID {bot_process.pid}")
        return jsonify({"status": "success", "message": "Bot de Twitch iniciado correctamente"})
    except Exception as e:
        debug_log(f"Error al iniciar el bot de Twitch: {str(e)}")
        return jsonify({"status": "error", "message": f"Error al iniciar el bot de Twitch: {str(e)}"})

@app.route('/stop_twitch_bot')
@login_required
def stop_twitch_bot():
    debug_log("Iniciando proceso de detención del bot de Twitch")
    
    twitch_pid, _ = get_bot_pids()
    if twitch_pid:
        try:
            debug_log(f"Enviando señal SIGTERM al proceso Twitch con PID {twitch_pid}")
            os.kill(twitch_pid, signal.SIGTERM)
            debug_log("Señal SIGTERM enviada correctamente al bot de Twitch")
            
            # Eliminar el archivo PID si existe
            if os.path.exists('twitch_bot.pid'):
                try:
                    os.remove('twitch_bot.pid')
                    debug_log("Archivo twitch_bot.pid eliminado correctamente")
                except Exception as e:
                    debug_log(f"Error al eliminar archivo twitch_bot.pid: {str(e)}")
            
            return jsonify({"status": "success", "message": "Bot de Twitch detenido correctamente"})
        except Exception as e:
            debug_log(f"Error al detener el bot de Twitch: {str(e)}")
            return jsonify({"status": "error", "message": f"Error al detener el bot de Twitch: {str(e)}"})
    else:
        debug_log("Intento de detener el bot de Twitch, pero no se encontró ningún proceso en ejecución")
        # Eliminar el archivo PID si existe, aunque no se encontró el proceso
        if os.path.exists('twitch_bot.pid'):
            try:
                os.remove('twitch_bot.pid')
                debug_log("Archivo twitch_bot.pid eliminado aunque no se encontró el proceso")
            except Exception as e:
                debug_log(f"Error al eliminar archivo twitch_bot.pid: {str(e)}")
        return jsonify({"status": "error", "message": "El bot de Twitch no está en ejecución"})

@app.route('/start_discord_bot')
@login_required
def start_discord_bot():
    global discord_bot_process
    
    debug_log("Iniciando proceso de arranque del bot de Discord")
    
    # Verificar si el bot ya está en ejecución
    _, discord_pid = get_bot_pids()
    if discord_pid:
        debug_log(f"El bot de Discord ya está en ejecución con PID {discord_pid}, cancelando arranque")
        return jsonify({"status": "error", "message": "El bot de Discord ya está en ejecución"})
    
    # Iniciar el bot de Discord
    try:
        debug_log("Intentando iniciar proceso del bot de Discord")
        discord_bot_process = subprocess.Popen(['python', 'discordbot.py'])
        debug_log(f"Bot de Discord iniciado correctamente con PID {discord_bot_process.pid}")
        return jsonify({"status": "success", "message": "Bot de Discord iniciado correctamente"})
    except Exception as e:
        debug_log(f"Error al iniciar el bot de Discord: {str(e)}")
        return jsonify({"status": "error", "message": f"Error al iniciar el bot de Discord: {str(e)}"})

@app.route('/stop_discord_bot')
@login_required
def stop_discord_bot():
    debug_log("Iniciando proceso de detención del bot de Discord")
    
    _, discord_pid = get_bot_pids()
    if discord_pid:
        try:
            debug_log(f"Enviando señal SIGTERM al proceso Discord con PID {discord_pid}")
            os.kill(discord_pid, signal.SIGTERM)
            debug_log("Señal SIGTERM enviada correctamente al bot de Discord")
            
            # Eliminar el archivo PID si existe
            if os.path.exists('discord_bot.pid'):
                try:
                    os.remove('discord_bot.pid')
                    debug_log("Archivo discord_bot.pid eliminado correctamente")
                except Exception as e:
                    debug_log(f"Error al eliminar archivo discord_bot.pid: {str(e)}")
            
            return jsonify({"status": "success", "message": "Bot de Discord detenido correctamente"})
        except Exception as e:
            debug_log(f"Error al detener el bot de Discord: {str(e)}")
            return jsonify({"status": "error", "message": f"Error al detener el bot de Discord: {str(e)}"})
    else:
        debug_log("Intento de detener el bot de Discord, pero no se encontró ningún proceso en ejecución")
        # Eliminar el archivo PID si existe, aunque no se encontró el proceso
        if os.path.exists('discord_bot.pid'):
            try:
                os.remove('discord_bot.pid')
                debug_log("Archivo discord_bot.pid eliminado aunque no se encontró el proceso")
            except Exception as e:
                debug_log(f"Error al eliminar archivo discord_bot.pid: {str(e)}")
        return jsonify({"status": "error", "message": "El bot de Discord no está en ejecución"})

@app.route('/restart_twitch_bot')
@login_required
def restart_twitch_bot():
    debug_log("Iniciando reinicio del bot de Twitch")
    response_stop = stop_twitch_bot()
    debug_log(f"Resultado de detención del bot de Twitch: {response_stop.get_json()}")
    # Pequeña pausa para asegurar que el proceso anterior termine completamente
    import time
    time.sleep(1)
    
    # Verificar que el archivo PID ha sido eliminado antes de iniciar el nuevo proceso
    if os.path.exists('twitch_bot.pid'):
        try:
            os.remove('twitch_bot.pid')
            debug_log("Archivo twitch_bot.pid eliminado antes de reiniciar")
        except Exception as e:
            debug_log(f"Error al eliminar archivo twitch_bot.pid antes de reiniciar: {str(e)}")
    
    response_start = start_twitch_bot()
    debug_log(f"Resultado de inicio del bot de Twitch: {response_start.get_json()}")
    return response_start

@app.route('/restart_discord_bot')
@login_required
def restart_discord_bot():
    debug_log("Iniciando reinicio del bot de Discord")
    response_stop = stop_discord_bot()
    debug_log(f"Resultado de detención del bot de Discord: {response_stop.get_json()}")
    # Pequeña pausa para asegurar que el proceso anterior termine completamente
    import time
    time.sleep(1)
    
    # Verificar que el archivo PID ha sido eliminado antes de iniciar el nuevo proceso
    if os.path.exists('discord_bot.pid'):
        try:
            os.remove('discord_bot.pid')
            debug_log("Archivo discord_bot.pid eliminado antes de reiniciar")
        except Exception as e:
            debug_log(f"Error al eliminar archivo discord_bot.pid antes de reiniciar: {str(e)}")
    
    response_start = start_discord_bot()
    debug_log(f"Resultado de inicio del bot de Discord: {response_start.get_json()}")
    return response_start

@app.route('/clear_twitch_memory')
@login_required
def clear_twitch_memory():
    debug_log("Iniciando proceso de limpieza de memoria del bot de Twitch")
    try:
        # Obtener el PID del bot de Twitch
        twitch_pid, _ = get_bot_pids()
        if not twitch_pid:
            debug_log("No se encontró el PID del bot de Twitch para limpiar memoria")
            return jsonify({"status": "error", "message": "El bot de Twitch no está en ejecución"})
        
        debug_log(f"Intentando enviar señal SIGUSR1 al proceso Twitch con PID {twitch_pid}")
        # Enviar señal para reiniciar la memoria
        if send_reset_memory_signal(twitch_pid):
            debug_log(f"Señal para limpiar memoria enviada correctamente al bot de Twitch con PID {twitch_pid}")
            return jsonify({"status": "success", "message": "Memoria del bot de Twitch reiniciada correctamente"})
        else:
            debug_log(f"Error al enviar señal para limpiar memoria al bot de Twitch con PID {twitch_pid}")
            return jsonify({"status": "error", "message": "Error al enviar la señal para reiniciar la memoria"})
    except Exception as e:
        debug_log(f"Excepción al reiniciar la memoria del bot de Twitch: {str(e)}")
        return jsonify({"status": "error", "message": f"Error al reiniciar la memoria del bot de Twitch: {str(e)}"})

@app.route('/clear_discord_memory')
@login_required
def clear_discord_memory():
    debug_log("Iniciando proceso de limpieza de memoria del bot de Discord")
    try:
        # Obtener el PID del bot de Discord
        _, discord_pid = get_bot_pids()
        if not discord_pid:
            debug_log("No se encontró el PID del bot de Discord para limpiar memoria")
            return jsonify({"status": "error", "message": "El bot de Discord no está en ejecución"})
        
        debug_log(f"Intentando enviar señal SIGUSR1 al proceso Discord con PID {discord_pid}")
        # Enviar señal para reiniciar la memoria
        if send_reset_memory_signal(discord_pid):
            debug_log(f"Señal para limpiar memoria enviada correctamente al bot de Discord con PID {discord_pid}")
            return jsonify({"status": "success", "message": "Memoria del bot de Discord reiniciada correctamente"})
        else:
            debug_log(f"Error al enviar señal para limpiar memoria al bot de Discord con PID {discord_pid}")
            return jsonify({"status": "error", "message": "Error al enviar la señal para reiniciar la memoria"})
    except Exception as e:
        debug_log(f"Excepción al reiniciar la memoria del bot de Discord: {str(e)}")
        return jsonify({"status": "error", "message": f"Error al reiniciar la memoria del bot de Discord: {str(e)}"})

if __name__ == '__main__':
    # Crear el directorio de templates si no existe
    if not os.path.exists('templates'):
        os.makedirs('templates')
        debug_log("Directorio de templates creado")
    
    debug_log("Creando archivos de plantillas HTML")
    
    # Crear la plantilla HTML de login
    with open('templates/login.html', 'w') as f:
        f.write('''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Panel de Control de Bots</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .card {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 10px 15px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
            width: 100%;
        }
        .error {
            color: #f44336;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <h1>Panel de Control de Bots</h1>
    
    <div class="card">
        <h2>Iniciar Sesión</h2>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form method="post">
            <div class="form-group">
                <label for="username">Usuario:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Contraseña:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Iniciar Sesión</button>
        </form>
    </div>
</body>
</html>''')
    debug_log("Plantilla login.html creada")
    
    # Crear la plantilla HTML básica
    with open('templates/index.html', 'w') as f:
        f.write('''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Control de Bots</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .card {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
            margin-bottom: 20px;
        }
        .bot-status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .status {
            padding: 5px 10px;
            border-radius: 4px;
            font-weight: bold;
        }
        .running {
            background-color: #d4edda;
            color: #155724;
        }
        .stopped {
            background-color: #f8d7da;
            color: #721c24;
        }
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 10px 15px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        button.stop {
            background-color: #f44336;
        }
        button.restart {
            background-color: #2196F3;
        }
        button.clear {
            background-color: #ff9800;
        }
        button.logout {
            background-color: #607d8b;
            float: right;
        }
        .buttons {
            display: flex;
            justify-content: space-between;
        }
        .alert {
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
            display: none;
        }
        .alert-success {
            background-color: #d4edda;
            color: #155724;
        }
        .alert-error {
            background-color: #f8d7da;
            color: #721c24;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Panel de Control de Bots</h1>
        <a href="/logout"><button class="logout">Cerrar Sesión</button></a>
    </div>
    
    <div id="alert" class="alert"></div>
    
    <div class="card">
        <h2>Bot de Twitch</h2>
        <div class="bot-status">
            <span>Estado: <span class="status {{ 'running' if twitch_status == 'En ejecución' else 'stopped' }}">{{ twitch_status }}</span></span>
        </div>
        <div class="buttons">
            <button id="start-twitch" onclick="controlBot('start_twitch_bot')">Iniciar</button>
            <button id="stop-twitch" class="stop" onclick="controlBot('stop_twitch_bot')">Detener</button>
            <button id="restart-twitch" class="restart" onclick="controlBot('restart_twitch_bot')">Reiniciar</button>
            <button id="clear-twitch-memory" class="clear" onclick="controlBot('clear_twitch_memory')">Borrar Memoria</button>
        </div>
    </div>
    
    <div class="card">
        <h2>Bot de Discord</h2>
        <div class="bot-status">
            <span>Estado: <span class="status {{ 'running' if discord_status == 'En ejecución' else 'stopped' }}">{{ discord_status }}</span></span>
        </div>
        <div class="buttons">
            <button id="start-discord" onclick="controlBot('start_discord_bot')">Iniciar</button>
            <button id="stop-discord" class="stop" onclick="controlBot('stop_discord_bot')">Detener</button>
            <button id="restart-discord" class="restart" onclick="controlBot('restart_discord_bot')">Reiniciar</button>
            <button id="clear-discord-memory" class="clear" onclick="controlBot('clear_discord_memory')">Borrar Memoria</button>
        </div>
    </div>

    <script>
        function controlBot(action) {
            fetch('/' + action)
                .then(response => response.json())
                .then(data => {
                    const alert = document.getElementById('alert');
                    alert.textContent = data.message;
                    alert.className = data.status === 'success' ? 'alert alert-success' : 'alert alert-error';
                    alert.style.display = 'block';
                    
                    // Ocultar la alerta después de 3 segundos
                    setTimeout(() => {
                        alert.style.display = 'none';
                    }, 3000);
                    
                    // Recargar la página para actualizar los estados
                    setTimeout(() => {
                        location.reload();
                    }, 1000);
                })
                .catch(error => {
                    console.error('Error:', error);
                    const alert = document.getElementById('alert');
                    alert.textContent = 'Error al comunicarse con el servidor';
                    alert.className = 'alert alert-error';
                    alert.style.display = 'block';
                });
        }
    </script>
</body>
</html>''')
    debug_log("Plantilla index.html creada")
    
    # Información de inicio del servidor
    debug_log("Iniciando servidor Flask en 0.0.0.0:5555")
    # Iniciar el servidor Flask
    app.run(host='0.0.0.0', port=5555, debug=True)
