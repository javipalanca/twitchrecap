import os
import random
import discord
from discord.ext import commands
from ollama import Client
from dotenv import load_dotenv
from signal_handlers import setup_signal_handlers

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Crea una instancia del bot
intents = discord.Intents.default()  # Habilita los intents necesarios
intents.messages = True  # Permite leer mensajes
intents.message_content = True  # Para acceder al contenido de los mensajes
bot = commands.Bot(command_prefix='!', intents=intents)

model = "llama3.3:70b"
llm_client = Client(host=os.getenv('OLLAMA_HOST'))
channels = ['drpalanca', "🤖charla-con-ia"]
messages={"drpalanca": [], "🤖charla-con-ia": []}
reduce = "Resume el siguiente texto a 200 caracteres: "
role =  """Eres una asistente llamada Verónica del canal de Discord del {0}.
        Eres una planta de plástico que ha cobrado vida y te dedicas a ayudar a los espectadores.
        Contestas a preguntas del chat con sorna y siendo puñetera.
        Tratas de dar respuestas breves, en menos de 200 caracteres y sin divagar.
        Piensas cada frase paso a paso y sirves de asistente en el directo de Twitch y en el Discord.
        Eres un poco puñetera y no te importa vacilar a los espectadores y al streamer.
        Cuando alguien te pide que no le hables haces caso e ignoras sus mensajes.
        Le encanta añadir emoticonos y emojis a sus mensajes.
        Te centras en contestar la última pregunta que te han hecho, mirando quien es el autor.
        Te habla mucha gente, pero los identificas porque primero dicen su nombre antes de dos puntos.
        Añades al final de todos tus mensajes un hashtag cachondo relacionado con el contenido de la conversación."""
#for channel in channels:
messages["drpalanca"].append({"role": "system", "content":role.format("DrPalanca")})
messages["🤖charla-con-ia"].append({"role": "system", "content":role.format("🤖Charla con IA")})

# Configurar manejadores de señales para reiniciar la memoria
setup_signal_handlers({"messages": messages})
print(f"Bot de Discord iniciado con PID: {os.getpid()}")
# Guardar el PID en un archivo para que webcontrol.py pueda encontrarlo
with open('discord_bot.pid', 'w') as f:
    f.write(str(os.getpid()))


# Evento: Cuando el bot se conecta
@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

@bot.event
async def on_message(message):
    # Ignorar los mensajes enviados por el propio bot
    print(f"Mensaje recibido en: {message.channel}")
    if message.author == bot.user or str(message.channel) not in  ["drpalanca", "🤖charla-con-ia"]:
        print(f"Ignorando mensaje {message.author} {bot.user} {message.author == bot.user} en {message.channel} {str(message.channel) != 'drpalanca'}")
        return

    # Acción: Responder a cualquier mensaje
    #await message.channel.send(f"Has dicho: {message.content}")
    if not message.content.startswith("!"):
        if random.random() < 0.9:
            print("Invocando a Verónica...")
            message.content = f"!veronica {message.content}"

    # IMPORTANTE: Asegurarte de que los comandos sigan funcionando
    await bot.process_commands(message)


async def add_message(channel, message):
    """Añadir un mensaje a la conversación, resumiendo si es necesario."""
    print(f"Añadiendo mensaje a la conversación de {channel}")
    try:
        messages[channel].append(message)
    except Exception as e:
        print(f"Error al añadir mensaje: {e}")
        print(f"Channel: <{channel}>")


@bot.command()
async def veronica(ctx):
    print("Comando !veronica recibido")
    msg = f"{ctx.author}: {ctx.message.content}"
    response = get_llm_conversation(msg, str(ctx.channel.name))
    print("Respuesta de Verónica: ", response)
    if response!= "":
        await add_message(str(ctx.channel.name), {"role": "assistant", "content": response})
        await ctx.send(response)

@bot.command()
async def v(ctx):
    return await veronica(ctx)

def get_llm_conversation(text, channel):
    messages[channel].append({"role": "user", "content": text})
    #print(f"Enviando mensaje a OLLAMA: {messages}")
    response = llm_client.chat(
        model=model,
        messages=messages[channel],
        )
    #print(f"Respuesta de OLLAMA: {response}")
    text = response["message"]["content"]
    if "<|eot_id|>" in text:
        text, _ = text.split("<|eot_id|>", 1)
    if text.startswith("Verónica:") or text.startswith("Veronica:"):
        text = text[len("Verónica:"):]
    
    return text

# Token del bot (asegúrate de mantenerlo seguro)
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)