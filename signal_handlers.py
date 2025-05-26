#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import signal
import time

# Señal personalizada para reiniciar la memoria del bot
SIGUSR1 = 10  # SIGUSR1 en sistemas Unix

def setup_signal_handlers(bot_instance):
    """Configura los manejadores de señales para el bot"""
    
    def handle_reset_memory(signum, frame):
        """Manejador de la señal para reiniciar la memoria"""
        print("Recibida señal para reiniciar la memoria")
        
        # Determinar la estructura de datos del bot
        if hasattr(bot_instance, 'messages'):  # Bot de Twitch
            # Reinicia la memoria pero mantén los mensajes del sistema
            for channel in bot_instance.messages:
                # Guarda solo el mensaje del sistema si existe
                system_messages = [msg for msg in bot_instance.messages[channel] if msg.get('role') == 'system']
                bot_instance.messages[channel] = system_messages
        elif isinstance(bot_instance, dict) and 'messages' in bot_instance:  # Bot de Discord
            # Reinicia la memoria pero mantén los mensajes del sistema
            messages = bot_instance['messages']
            for channel in messages:
                # Guarda solo el mensaje del sistema si existe
                system_messages = [msg for msg in messages[channel] if msg.get('role') == 'system']
                messages[channel] = system_messages
        
        print("Memoria reiniciada correctamente")
    
    # Registra el manejador para la señal SIGUSR1
    signal.signal(SIGUSR1, handle_reset_memory)
    
    print(f"Manejador de señales configurado. PID: {os.getpid()}")

def send_reset_memory_signal(pid):
    """Envía una señal al proceso para reiniciar la memoria"""
    try:
        os.kill(pid, SIGUSR1)
        return True
    except Exception as e:
        print(f"Error al enviar señal: {e}")
        return False
