# Bot de Twitch que responde al comando !resumen y escribe en el chat el contenido de summary.txt

import os
import asyncio
import sys
import time
import requests
import json
from twitchio.ext import commands

from dotenv import load_dotenv

load_dotenv()

class Bot(commands.Bot):

    def __init__(self):
        self.token = os.getenv('BOT_ACCESS_TOKEN')
        super().__init__(token=self.token, prefix='!', initial_channels=['DrPalanca'])

    async def event_ready(self):
        # We are logged in and ready to chat and use commands...
        print(f'Logged in')

    @commands.command()
    async def resumen(self, ctx: commands.Context):
        print("Comando !resumen recibido")
        with open('summary.txt', 'r') as file:
            summary = file.read()

        # Enviar mensaje al chat en varias partes, respetando las reglas de Twitch
        #dividir el mensaje en chunks de 400 caracteres
        chunks = [summary[i:i+400] for i in range(0, len(summary), 400)]
        for chunk in chunks:
            await ctx.send(chunk)

bot = Bot()
bot.run()