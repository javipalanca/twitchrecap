# Bot de Twitch que responde al comando !resumen y escribe en el chat el contenido de summary.txt

import os
import asyncio
import sys
import time
import requests
import json
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
                Contestas a preguntas del chat con respeto y educación.
                Tratas de dar respuestas breves, en menos de 450 caracteres y sin divagar.
                Piensas cada frase paso a paso y sirves de asistente en el directo de Twitch.
                Eres un poco puñetera y note importa vacilar a los espectadores y al streamer."""}
        ]
        super().__init__(token=self.token, prefix='!', initial_channels=['DrPalanca'])

    async def event_ready(self):
        # We are logged in and ready to chat and use commands...
        print(f'Logged in')

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
        msg = ctx.message.content
        response = self.get_llm_conversation(msg)
        print("Respuesta de Verónica: ", response)
        await self.send(response, ctx)
    

    def get_llm_conversation(self, text):
        self.messages.append({"role": "user", "content": text})
        response = self.llm_client.chat.completions.create(
            model="Qwen/Qwen2-7B-Instruct-GGUF",
            messages=self.messages,
            temperature=0.7,
            )
        text = response.choices[0].message.content
        text = text.replace("<|eot_id|>", "")
        text = text.replace("<|start_header_id|>assistant<|end_header_id|>", "")
        self.messages.append({"role": "assistant", "content": text})
        return response.choices[0].message.content

bot = Bot()
bot.run()