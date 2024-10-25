# Bot de Twitch que responde al comando !resumen y escribe en el chat el contenido de summary.txt

import os
import asyncio
import sys
import time
import requests
import json
import aiohttp
import bs4
from openai import OpenAI
from twitchio.ext import commands

from dotenv import load_dotenv

load_dotenv()

class Bot(commands.Bot):

    def __init__(self):
        self.token = os.getenv('BOT_ACCESS_TOKEN')
        self.llm_client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
        self.channels = ['drpalanca', 'tato_escriche', 'disten_']
        self.messages={}
        self.reduce = "Resume el siguiente texto a 200 caracteres: "
        self.role =  """Eres una asistente llamada Verónica del canal de Twitch del {0}.
                Eres una planta de plástico que ha cobrado vida y te dedicas a ayudar a los espectadores.
                Contestas a preguntas del chat con sorna y siendo puñetera.
                Tratas de dar respuestas breves, en menos de 200 caracteres y sin divagar.
                Piensas cada frase paso a paso y sirves de asistente en el directo de Twitch.
                Eres un poco puñetera y no te importa vacilar a los espectadores y al streamer.
                Te centras en contestar la última pregunta que te han hecho.
                Te habla mucha gente, pero los identificas porque primero dicen su nombre antes de dos puntos."""
        for channel in self.channels:
            self.messages[channel] = [{"role": "system", "content":self.role.format(channel)}]
        super().__init__(token=self.token, prefix='!', initial_channels=self.channels)
        

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
        self.messages[channel].append(message)


    async def event_message(self, ctx):
        if ctx.author:
            print(f'[{ctx.channel.name}] {ctx.author.name}: {ctx.content}')
            message = {"role": "user", "content": f'{ctx.author.name}: {ctx.content}'}
            await self.add_message(ctx.channel.name, message)
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
            response = self.llm_client.chat.completions.create(
                model="Qwen/Qwen2-7B-Instruct-GGUF",
                messages=messages,
                temperature=0.4,
            )
            message = response.choices[0].message.content
        
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
        msg = ctx.message.content
        msg = f"{ctx.author.name}: {msg}"
        response = self.get_llm_conversation(msg, ctx.channel.name)
        print("Respuesta de Verónica: ", response)
        await self.add_message(ctx.channel.name, {"role": "assistant", "content": response})
        await self.send(response, ctx)

    @commands.command()
    async def v(self, ctx: commands.Context):
        return await self.veronica(ctx)
    

    def get_llm_conversation(self, text, channel, messages=None):
        response = self.llm_client.chat.completions.create(
            model="Qwen/Qwen2-7B-Instruct-GGUF",
            messages=messages if messages is not None else self.messages[channel],
            temperature=0.7,
            )
        text = response.choices[0].message.content
        if "<|eot_id|>" in text:
            text, _ = text.split("<|eot_id|>", 1)
        if text.startswith("Verónica:") or text.startswith("Veronica:"):
            text = text[len("Verónica:"):]
        
        return text
bot = Bot()
bot.run()