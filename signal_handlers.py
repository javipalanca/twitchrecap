#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import time
import datetime

# Señal personalizada para reiniciar la memoria del bot
SIGUSR1 = 10  # SIGUSR1 en sistemas Unix

# Configuración de registro de depuración
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

def debug_log(message):
    """Función centralizada para registrar mensajes de depuración"""
    if DEBUG:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DEBUG][SignalHandler] {timestamp} - {message}")

def setup_signal_handlers(bot_instance):
    """Configura los manejadores de señales para el bot"""
    
    def handle_reset_memory(signum, frame):
        """Manejador de la señal para reiniciar la memoria"""
        debug_log(f"Recibida señal {signum} para reiniciar la memoria")
        
        # Determinar la estructura de datos del bot
        if hasattr(bot_instance, 'messages'):  # Bot de Twitch
            debug_log("Detectado bot de Twitch, reiniciando mensajes")
            # Reinicia la memoria pero mantén los mensajes del sistema
            for channel in bot_instance.messages:
                debug_log(f"Reiniciando memoria para el canal: {channel}")
                # Guarda solo el mensaje del sistema si existe
                system_messages = [msg for msg in bot_instance.messages[channel] if msg.get('role') == 'system']
                previous_count = len(bot_instance.messages[channel])
                bot_instance.messages[channel] = system_messages
                debug_log(f"Canal {channel}: {previous_count} mensajes eliminados, {len(system_messages)} mensajes del sistema conservados")
        elif isinstance(bot_instance, dict) and 'messages' in bot_instance:  # Bot de Discord
            debug_log("Detectado bot de Discord, reiniciando mensajes")
            # Reinicia la memoria pero mantén los mensajes del sistema
            messages = bot_instance['messages']
            for channel in messages:
                debug_log(f"Reiniciando memoria para el canal: {channel}")
                # Guarda solo el mensaje del sistema si existe
                system_messages = [msg for msg in messages[channel] if msg.get('role') == 'system']
                previous_count = len(messages[channel])
                messages[channel] = system_messages
                debug_log(f"Canal {channel}: {previous_count} mensajes eliminados, {len(system_messages)} mensajes del sistema conservados")
        else:
            debug_log("Estructura de bot no reconocida, no se pudo reiniciar la memoria correctamente")
        
        debug_log("Memoria reiniciada correctamente")
    
    # Registra el manejador para la señal SIGUSR1
    signal.signal(SIGUSR1, handle_reset_memory)
    
    debug_log(f"Manejador de señales configurado para proceso con PID: {os.getpid()}")
    
    # Guardar el PID en un archivo
    bot_type = "twitch_bot" if hasattr(bot_instance, 'messages') else "discord_bot"
    pid_file = f"{bot_type}.pid"
    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        debug_log(f"PID {os.getpid()} guardado en archivo {pid_file}")
    except Exception as e:
        debug_log(f"Error al guardar PID en archivo {pid_file}: {e}")

def send_reset_memory_signal(pid):
    """Envía una señal al proceso para reiniciar la memoria"""
    debug_log(f"Intentando enviar señal SIGUSR1 al proceso con PID: {pid}")
    
    try:
        # Primero verificamos que el proceso existe
        os.kill(pid, 0)  # Señal 0 solo verifica que el proceso existe
        debug_log(f"Proceso con PID {pid} existe, enviando señal SIGUSR1")
        
        # Enviamos la señal para reiniciar memoria
        os.kill(pid, SIGUSR1)
        debug_log(f"Señal SIGUSR1 enviada correctamente al proceso con PID {pid}")
        
        # Esperar un momento para asegurarse de que la señal se procese
        time.sleep(0.5)
        
        # Verificar que el proceso sigue existiendo después de la señal
        try:
            os.kill(pid, 0)
            debug_log(f"Proceso con PID {pid} sigue en ejecución después de enviar la señal")
            return True
        except OSError as e:
            debug_log(f"El proceso con PID {pid} ya no existe después de enviar la señal: {e}")
            return False
            
    except OSError as e:
        debug_log(f"Error al enviar señal al proceso con PID {pid}: {e}")
        return False
    except Exception as e:
        debug_log(f"Error inesperado al enviar señal: {e}")
        return False
