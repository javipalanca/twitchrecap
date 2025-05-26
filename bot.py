# Bot de Twitch que responde al comando !resumen y escribe en el chat el contenido de summary.txt

import os
import asyncio
import sys
import time
import requests
import json
import aiohttp
import bs4
import random
from openai import OpenAI
from ollama import Client
from twitchio.ext import commands
from watchdog.observers import Observer

from dotenv import load_dotenv
from signal_handlers import setup_signal_handlers

from watcher import SRTDirectoryHandler

load_dotenv()
model = "llama4:scout" #"llama3.3:70b"

def get_token():
    params = {
        'client_id': os.getenv('TWITCH_CLIENT_ID'),
        'client_secret': os.getenv('TWITCH_CLIENT_SECRET'),
        'grant_type': 'client_credentials'
    }
    response = requests.post('https://id.twitch.tv/oauth2/token', params=params)
    token = response.json()['access_token']
    print(f"Token: {token}")
    return token


class Bot(commands.Bot):

    def __init__(self):
        self.token = os.getenv('BOT_ACCESS_TOKEN')
        #self.llm_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
        self.llm_client = Client(host=os.getenv('OLLAMA_HOST'))
        self.channels = ['drpalanca'] #, "MarshallFlashMusic".lower(), 'tato_escriche', 'disten_', "jurgen_ator", "tiavioligaming", "outatime_videogames"]
        self.messages={}
        self.reduce = "Resume el siguiente texto a 200 caracteres: "
        self.role =  """Eres una asistente llamada Verónica del canal de Twitch del {0}.
                Eres una planta de plástico que ha cobrado vida y te dedicas a ayudar a los espectadores.
                Contestas a preguntas del chat con sorna y siendo puñetera.
                Tratas de dar respuestas breves, en menos de 200 caracteres y sin divagar.
                Piensas cada frase paso a paso y sirves de asistente en el directo de Twitch.
                Eres un poco puñetera y no te importa vacilar a los espectadores y al streamer.
                Verónica ha estado un tiempo fuera porque banearon a Verónica, pero por fin ha vuelto.
                Cuando alguien te pide que no le hables haces caso e ignoras sus mensajes.
                Cuando quieres que tu mensaje se lea en voz alta, empiezas con un !speak 
                Le encanta añadir emoticonos y emojis a sus mensajes.
                Te centras en contestar la última pregunta que te han hecho, mirando quien es el autor.
                Te habla mucha gente, pero los identificas porque primero dicen su nombre antes de dos puntos.
                Añades al final de todos tus mensajes un hashtag cachondo relacionado con el contenido de la conversación."""
        for channel in self.channels:
            self.messages[channel] = [{"role": "system", "content":self.role.format(channel)}]
        super().__init__(token=os.getenv("OAUTH_TOKEN"),
                         client_id=os.getenv("BOT_CLIENT_ID"),
                         prefix='!', initial_channels=self.channels)
        self.message_count = 0
        self.message_timestamps = []
        
        # Configurar manejadores de señales para reiniciar la memoria
        setup_signal_handlers(self)
        print(f"Bot de Twitch iniciado con PID: {os.getpid()}")
        # Guardar el PID en un archivo para que webcontrol.py pueda encontrarlo
        with open('twitch_bot.pid', 'w') as f:
            f.write(str(os.getpid()))


    async def event_ready(self):
        # We are logged in and ready to chat and use commands...
        print(f'Logged in')

    async def summarize_conversation(self, channel):
        """Resumir la conversación actual y actualizar messages."""
        conversation = " ".join([msg["content"] for msg in self.messages[channel]])
        prompt = self.reduce + conversation
        messages = [{"role": "system", "content": "Eres un asistente de resumenes. Resumes conversaciones sin introducir ruido adicional."}]
        response = self.get_llm_conversation(prompt, channel, messages=messages)
        self.messages[channel] = [
            {"role": "system", "content": self.role.format(channel), 
             "role": "user", "content": response}
            ]
        print(f"Resumen de la conversación: {response}")

    async def add_message(self, channel, message):
        """Añadir un mensaje a la conversación, resumiendo si es necesario."""
        print(f"Añadiendo mensaje a la conversación de {channel}")
        #if len(self.messages[channel]) > 25:  # Suponiendo un límite de 50 mensajes
        #    print("Resumiendo conversación...")
        #    await self.summarize_conversation(channel)
        try:
            self.messages[channel].append(message)
        except Exception as e:
            print(f"Error al añadir mensaje: {e}")
            print(f"Channel: <{channel}>")
            print(f"Messages: ", self.messages.keys())
            print(f"Asserting...{channel in self.messages.keys()}")


    async def event_message(self, ctx):
        if ctx.author:
            print(f'[{ctx.channel.name}] {ctx.author.name}: {ctx.content}')
            message = {"role": "user", "content": f'{ctx.author.name}: {ctx.content}'}
            await self.add_message(ctx.channel.name, message)

            if not ctx.content.startswith("!"):
                if random.random() < 0.15: # and len(self.message_timestamps) < 5:
                    print("Invocando a Verónica...")
                    current_time = time.time()
                    self.message_timestamps = [timestamp for timestamp in self.message_timestamps if current_time - timestamp < 60]
                    ctx.content = f"!veronica {ctx.content}"
                    self.message_timestamps.append(time.time())
            # No olvides de procesar los comandos
            await bot.handle_commands(ctx)

    async def send(self, message, ctx):
        # Enviar mensaje al chat en varias partes, respetando las reglas de Twitch
        #dividir el mensaje en chunks de 400 caracteres
        if len(message) > 400:
            messages = [
                {"role": "system", "content": "Eres el bot Veronica que se dedica únicamente a resumir, sin introducir ruido adicional, los mensajes, por lo que no cambias nunca ni los tiempos verbales ni las personas."},
                {"role": "user", "content": self.reduce + message}
                ]
            #response = self.llm_client.chat.completions.create(
            response = self.llm_client.chat(
                model=model,
                messages=messages,
                #temperature=0.4,
            )
            #message = response.choices[0].message.content
            message = response["message"]["content"]
        
        try:
            # Dividir el mensaje en chunks de 400 caracteres sin cortar palabras a la mitad
            words = message.split()
            chunks = []
            chunk = ""
            for word in words:
                if len(chunk) + len(word) + 1 > 400:
                    chunks.append(chunk)
                    chunk = word
                else:
                    chunk += " " + word if chunk else word
            chunks.append(chunk)  # Añadir el último chunk

            for chunk in chunks:
                await ctx.send(chunk)
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error al enviar mensaje: {e}")

    @commands.command()
    async def resumen(self, ctx: commands.Context):
        print("Comando !resumen recibido")
        with open('summary.txt', 'r') as file:
            summary = file.read()

        await self.send(summary, ctx)

    @commands.command()
    async def veronica(self, ctx: commands.Context):
        print("Comando !veronica recibido")
        #title, game = self.get_twitch_title_and_game("DrPalanca")
        #print("Título del stream: ", title, "Juego: ", game)
        msg = f"{ctx.author.name}: {ctx.message.content}"
        response = self.get_llm_conversation(msg, ctx.channel.name)
        print("Respuesta de Verónica: ", response)
        await self.add_message(ctx.channel.name, {"role": "assistant", "content": response})
        await self.send(response, ctx)

    @commands.command()
    async def v(self, ctx: commands.Context):
        return await self.veronica(ctx)
    

    def get_llm_conversation(self, text, channel, messages=None):
        #response = self.llm_client.chat.completions.create(
        response = self.llm_client.chat(
            #model="Qwen/Qwen2-7B-Instruct-GGUF",
            model=model,
            messages=messages if messages is not None else self.messages[channel],
            #temperature=0.7,
            )
        #text = response.choices[0].message.content
        text = response["message"]["content"]
        if "<|eot_id|>" in text:
            text, _ = text.split("<|eot_id|>", 1)
        if text.startswith("Verónica:") or text.startswith("Veronica:"):
            text = text[len("Verónica:"):]
        
        return text
    
    def get_most_recent_file_in_dir(self, dir):
        files = os.listdir(dir)
        files.sort(key=lambda x: os.path.getmtime(os.path.join(dir, x)))
        return files[-1]
    
    def watch_file(self, filename):
        while True:
            with open(filename, 'r') as file:
                text = file.read()
                if text:
                    print(f"Texto leído de {filename}: {text}")
                    return text
            time.sleep(1)
bot = Bot()
directory = "/Users/jpalanca/devel/twitchrecap/transcripts"
#event_handler = SRTDirectoryHandler(directory, bot)
#observer = Observer()
#observer.schedule(event_handler, path=directory, recursive=False)

#print(f"Monitorizando cambios en el directorio: {directory}")

# Iniciar el bot y el observer
#observer.start()
try:
    bot.run()
except KeyboardInterrupt:
    print("Bot stopped")
#observer.stop()
#observer.join()
print("Bot stopping...")