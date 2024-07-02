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
        self.messages=[
                {"role": "system",
                "content": """Eres una asistente llamada Verónica del canal de Twitch del DrPalanca.
                Eres una planta de plástico que ha cobrado vida y te dedicas a ayudar a los espectadores.
                Contestas a preguntas del chat con sorna y siendo puñetera.
                Tratas de dar respuestas breves, en menos de 200 caracteres y sin divagar.
                Piensas cada frase paso a paso y sirves de asistente en el directo de Twitch.
                Eres un poco puñetera y no te importa vacilar a los espectadores y al streamer."""}
        ]
        super().__init__(token=self.token, prefix='!', initial_channels=['DrPalanca', 'Tato_Escriche'])
        

    async def event_ready(self):
        # We are logged in and ready to chat and use commands...
        print(f'Logged in')

    async def event_message(self, ctx):
        if ctx.author:
            print(f'{ctx.author.name}: {ctx.content}')
            self.messages.append({"role": "user", "content": f'{ctx.author.name}: {ctx.content}'})
            # No olvides de procesar los comandos
            await bot.handle_commands(ctx)

    async def send(self, message, ctx):
        # Enviar mensaje al chat en varias partes, respetando las reglas de Twitch
        #dividir el mensaje en chunks de 400 caracteres
        chunks = [message[i:i+400] for i in range(0, len(message), 400)]
        for chunk in chunks:
            await ctx.send(chunk)

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
        response = self.get_llm_conversation(msg)
        print("Respuesta de Verónica: ", response)
        await self.send(response, ctx)

    @commands.command()
    async def v(self, ctx: commands.Context):
        return await self.veronica(ctx)
    

    def get_llm_conversation(self, text):
        self.messages.append({"role": "user", "content": text})
        response = self.llm_client.chat.completions.create(
            model="Qwen/Qwen2-7B-Instruct-GGUF",
            messages=self.messages,
            temperature=0.7,
            )
        text = response.choices[0].message.content
        if "<|eot_id|>" in text:
            text, _ = text.split("<|eot_id|>", 1)
        self.messages.append({"role": "assistant", "content": text})
        return text
bot = Bot()
bot.run()