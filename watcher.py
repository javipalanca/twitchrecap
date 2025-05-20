import os
import time
import re
from watchdog.events import FileSystemEventHandler
from twitchio import Message, Channel, Chatter


def create_context(bot, content, author="DrPalanca", channel_name="drpalanca"):
    class SimulatedAuthor:
        def __init__(self, name):
            self.name = name
            self.display_name = name
            self.is_broadcaster = True
            self._ws = bot._connection._websocket  # Websocket necesario para TwitchIO

    # Simular un canal con atributos asignables directamente
    class SimulatedChannel:
        def __init__(self, name):
            self.name = name

    # Crear un mensaje simulado
    return Message(
        author=SimulatedAuthor(author),
        channel=SimulatedChannel(channel_name),
        content=content,
        raw_data="",
        tags={},
        timestamp=time.time(),
    )


# Clase para manejar los archivos SRT
class SRTDirectoryHandler(FileSystemEventHandler):
    def __init__(self, directory, bot):
        self.directory = directory
        self.current_file = None
        self.last_position = 0
        self.bot = bot

    def on_modified(self, event):
        # Identificar el archivo .srt más reciente
        newest_file = self.get_newest_srt_file()
        if newest_file and newest_file != self.current_file:
            print(f"Nuevo archivo detectado: {newest_file}")
            self.current_file = newest_file
            self.last_position = 0  # Reinicia la posición al cambiar de archivo

        # Leer líneas nuevas del archivo actual
        if self.current_file:
            self.read_new_lines()

    def get_newest_srt_file(self):
        """Encuentra el archivo .srt más reciente en el directorio."""
        srt_files = [
            os.path.join(self.directory, f)
            for f in os.listdir(self.directory)
            if f.endswith(".srt")
        ]
        if not srt_files:
            return None
        return max(srt_files, key=os.path.getmtime)

    def read_new_lines(self):
        try:
            with open(self.current_file, "r", encoding="utf-8") as file:
                file.seek(self.last_position)  # Ir al último punto leído
                new_lines = file.readlines()
                self.last_position = file.tell()  # Actualizar la posición

                # Procesar las líneas para ignorar números y marcas de tiempo
                text_lines = self.extract_text_lines(new_lines)
                line = " ".join(text_lines).strip()
                if len(line) < 300:
                    print(f"Nueva línea de texto: {line.strip()}")
                    # Enviar la línea al chat mediante el bot
                    if self.bot:
                        ctx = create_context(self.bot, line)
                        self.bot.loop.create_task(self.bot.event_message(ctx))
        except Exception as e:
            print(f"Error leyendo el archivo: {e}")

    def extract_text_lines(self, lines):
        """
        Filtra solo las líneas de texto, eliminando números y marcas de tiempo.
        """
        text_lines = []
        for line in lines:
            line = line.strip()
            # Ignorar líneas que son números o marcas de tiempo
            if line.isdigit() or re.match(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$", line):
                continue
            if line:  # Solo agregar líneas no vacías
                text_lines.append(line)
        return text_lines