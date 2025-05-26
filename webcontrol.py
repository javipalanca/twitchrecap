import os
import signal
import subprocess
import psutil
import json
import secrets
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from signal_handlers import send_reset_memory_signal

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Genera una clave secreta aleatoria

# Configuración de autenticación
# Cambia estas credenciales a valores seguros
USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
PASSWORD = os.environ.get('ADMIN_PASSWORD', 'contraseña_segura')

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
    
    # Primero intentar leer los archivos PID si existen
    try:
        if os.path.exists('twitch_bot.pid'):
            with open('twitch_bot.pid', 'r') as f:
                twitch_pid = int(f.read().strip())
            # Verificar que el proceso existe
            try:
                os.kill(twitch_pid, 0)  # Señal 0 solo verifica que el proceso existe
            except OSError:
                twitch_pid = None  # El proceso no existe
    except Exception:
        pass
        
    try:
        if os.path.exists('discord_bot.pid'):
            with open('discord_bot.pid', 'r') as f:
                discord_pid = int(f.read().strip())
            # Verificar que el proceso existe
            try:
                os.kill(discord_pid, 0)  # Señal 0 solo verifica que el proceso existe
            except OSError:
                discord_pid = None  # El proceso no existe
    except Exception:
        pass
    
    # Si no se encontraron PIDs en los archivos, buscar en los procesos
    if not twitch_pid or not discord_pid:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'python' in cmdline[0]:
                    if len(cmdline) > 1 and 'bot.py' in cmdline[1]:
                        twitch_pid = proc.info['pid']
                    elif len(cmdline) > 1 and 'discordbot.py' in cmdline[1]:
                        discord_pid = proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    
    return twitch_pid, discord_pid

# Referencia a los procesos de los bots para acceder a sus objetos
twitch_bot_instance = None
discord_bot_instance = None

@app.route('/')
@login_required
def index():
    twitch_pid, discord_pid = get_bot_pids()
    twitch_status = "En ejecución" if twitch_pid else "Detenido"
    discord_status = "En ejecución" if discord_pid else "Detenido"
    
    return render_template('index.html', 
                          twitch_status=twitch_status, 
                          discord_status=discord_status)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == USERNAME and request.form['password'] == PASSWORD:
            session['logged_in'] = True
            flash('Has iniciado sesión correctamente')
            return redirect(request.args.get('next') or url_for('index'))
        else:
            error = 'Credenciales inválidas. Por favor, inténtalo de nuevo.'
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Has cerrado sesión')
    return redirect(url_for('login'))

@app.route('/start_twitch_bot')
@login_required
def start_twitch_bot():
    global bot_process
    
    # Verificar si el bot ya está en ejecución
    twitch_pid, _ = get_bot_pids()
    if twitch_pid:
        return jsonify({"status": "error", "message": "El bot de Twitch ya está en ejecución"})
    
    # Iniciar el bot de Twitch
    try:
        bot_process = subprocess.Popen(['python', 'bot.py'])
        return jsonify({"status": "success", "message": "Bot de Twitch iniciado correctamente"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al iniciar el bot de Twitch: {str(e)}"})

@app.route('/stop_twitch_bot')
@login_required
def stop_twitch_bot():
    twitch_pid, _ = get_bot_pids()
    if twitch_pid:
        try:
            os.kill(twitch_pid, signal.SIGTERM)
            return jsonify({"status": "success", "message": "Bot de Twitch detenido correctamente"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error al detener el bot de Twitch: {str(e)}"})
    else:
        return jsonify({"status": "error", "message": "El bot de Twitch no está en ejecución"})

@app.route('/start_discord_bot')
@login_required
def start_discord_bot():
    global discord_bot_process
    
    # Verificar si el bot ya está en ejecución
    _, discord_pid = get_bot_pids()
    if discord_pid:
        return jsonify({"status": "error", "message": "El bot de Discord ya está en ejecución"})
    
    # Iniciar el bot de Discord
    try:
        discord_bot_process = subprocess.Popen(['python', 'discordbot.py'])
        return jsonify({"status": "success", "message": "Bot de Discord iniciado correctamente"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al iniciar el bot de Discord: {str(e)}"})

@app.route('/stop_discord_bot')
@login_required
def stop_discord_bot():
    _, discord_pid = get_bot_pids()
    if discord_pid:
        try:
            os.kill(discord_pid, signal.SIGTERM)
            return jsonify({"status": "success", "message": "Bot de Discord detenido correctamente"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error al detener el bot de Discord: {str(e)}"})
    else:
        return jsonify({"status": "error", "message": "El bot de Discord no está en ejecución"})

@app.route('/restart_twitch_bot')
@login_required
def restart_twitch_bot():
    stop_twitch_bot()
    return start_twitch_bot()

@app.route('/restart_discord_bot')
@login_required
def restart_discord_bot():
    stop_discord_bot()
    return start_discord_bot()

@app.route('/clear_twitch_memory')
@login_required
def clear_twitch_memory():
    try:
        # Obtener el PID del bot de Twitch
        twitch_pid, _ = get_bot_pids()
        if not twitch_pid:
            return jsonify({"status": "error", "message": "El bot de Twitch no está en ejecución"})
        
        # Enviar señal para reiniciar la memoria
        if send_reset_memory_signal(twitch_pid):
            return jsonify({"status": "success", "message": "Memoria del bot de Twitch reiniciada correctamente"})
        else:
            return jsonify({"status": "error", "message": "Error al enviar la señal para reiniciar la memoria"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al reiniciar la memoria del bot de Twitch: {str(e)}"})

@app.route('/clear_discord_memory')
@login_required
def clear_discord_memory():
    try:
        # Obtener el PID del bot de Discord
        _, discord_pid = get_bot_pids()
        if not discord_pid:
            return jsonify({"status": "error", "message": "El bot de Discord no está en ejecución"})
        
        # Enviar señal para reiniciar la memoria
        if send_reset_memory_signal(discord_pid):
            return jsonify({"status": "success", "message": "Memoria del bot de Discord reiniciada correctamente"})
        else:
            return jsonify({"status": "error", "message": "Error al enviar la señal para reiniciar la memoria"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al reiniciar la memoria del bot de Discord: {str(e)}"})

if __name__ == '__main__':
    # Crear el directorio de templates si no existe
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
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
    
    # Iniciar el servidor Flask
    app.run(host='0.0.0.0', port=5555, debug=True)
