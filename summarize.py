import requests
import json
import datetime
from openai import OpenAI
import av
import whisper
import streamlink
import requests
import os
import tempfile
import tqdm
from moviepy.editor import concatenate_videoclips, VideoFileClip
import torchaudio
import librosa
from dotenv import load_dotenv
import sys
import torch

load_dotenv()

# Configuración de credenciales
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

class Recap:
    def __init__(self, username, openai_client, client_id=None, client_secret=None):
        self.username = username
        self.client_id = client_id
        self.client_secret = client_secret
        self.openai_client = openai_client
        self.access_token = None
        self.user_id = None

    # Obtener token de acceso de Twitch
    def get_twitch_token(self, client_id, client_secret):
        url = 'https://id.twitch.tv/oauth2/token'
        params = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url, params=params)
        response_data = response.json()
        if 'access_token' in response_data:
            return response_data['access_token']
        else:
            print(response_data)
            raise Exception("Error al obtener el token de acceso")

    # Obtener el user_id del nombre de usuario
    def get_user_id(self, username):
        self.access_token = self.get_twitch_token(self.client_id, self.client_secret)
        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self.access_token}'
        }
        url = f'https://api.twitch.tv/helix/users?login={username}'
        response = requests.get(url, headers=headers)
        data = response.json()
        if 'data' in data and len(data['data']) > 0:
            return data['data'][0]['id']
        else:
            print(data)
            raise Exception(f"No se encontró el User ID para el usuario {username}")

    # Obtener el último directo usando el user_id
    def get_last_stream(self):
        if self.access_token is None:
            self.access_token = self.get_twitch_token(self.client_id, self.client_secret)
        if self.user_id is None:
            self.user_id = self.get_user_id(self.username)
        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self.access_token}'
        }
        url = f'https://api.twitch.tv/helix/videos?user_id={self.user_id}&first=1'
        response = requests.get(url, headers=headers)
        data = response.json()
        if 'data' in data and len(data['data']) > 0:
            return data['data'][0]
        else:
            print(data)
            raise Exception("No se encontró ningún directo")


    # Obtener la URL del archivo .m3u8 del video
    def get_m3u8_url(self, video_id):
        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self.access_token}'
        }
        url = f'https://api.twitch.tv/helix/videos?id={video_id}'
        response = requests.get(url, headers=headers)
        data = response.json()
        if 'data' in data and len(data['data']) > 0:
            video_data = data['data'][0]
            playback_url = video_data['url']
            return playback_url
        else:
            print(data)
            raise Exception("No se encontró el archivo .m3u8 del video")

    def download_from_twitch(self, url, output_file, quality="best"):
        if quality == "audio":
            output_file = output_file + ".ts"
        streams = streamlink.streams(url)
        if quality in streams:
            stream = streams[quality]
            playlist_url = stream.url
            print(f"Downloading from {playlist_url}")

            # Descargar el archivo M3U8
            response = requests.get(playlist_url)
            playlist_content = response.text

            # Crear un directorio temporal para los segmentos
            os.makedirs('temp_segments', exist_ok=True)

            # Descargar cada segmento .ts
            segment_urls = []
            for line in tqdm.tqdm(playlist_content.splitlines()):
                if line.endswith('.ts'):
                    segment_url = os.path.join(os.path.dirname(playlist_url), line)
                    segment_urls.append(segment_url)
                    segment_response = requests.get(segment_url, stream=True)
                    number, extension = line.split('.')
                    line = f"{number:>07}.{extension}"
                    segment_path = os.path.join('temp_segments', line)
                    with open(segment_path, 'wb') as segment_file:
                        for chunk in segment_response.iter_content(chunk_size=8192):
                            if chunk:
                                segment_file.write(chunk)

            # Combinar los segmentos en un solo archivo
            with open(output_file, 'wb') as of:
                for segment_path in tqdm.tqdm(sorted(os.listdir('temp_segments'))):
                    segment_path_full = os.path.join('temp_segments', segment_path)
                    with open(segment_path_full, 'rb') as segment_file:
                        bytes = segment_file.read()
                        #print(f"Writing {len(bytes)} bytes from {segment_path} to {output_file}")
                        of.write(bytes)

            # Limpiar el directorio temporal
            for segment_file in os.listdir('temp_segments'):
                os.remove(os.path.join('temp_segments', segment_file))
            os.rmdir('temp_segments')

            print(f"Downloaded to {output_file}")
        else:
            print("No suitable streams found")



    def ts_to_wav(self, ts_path, wav_path):
        import av  # Asegurarse de que av está importado

        # Abrir el archivo multimedia
        container = av.open(ts_path)

        # Crear un contenedor de salida para el archivo WAV
        output_container = av.open(wav_path, 'w')

        # Iterar sobre los streams del contenedor de entrada
        for stream in container.streams:
            # Verificar si el stream es de audio
            if stream.type == 'audio':
                # Añadir el stream de audio al contenedor de salida
                output_stream = output_container.add_stream('pcm_s16le', rate=16000, channels=1)

                # Leer los paquetes del stream de audio
                for packet in container.demux(stream):
                    for frame in packet.decode():
                        # Re-codificar el frame para el nuevo stream
                        for packet in output_stream.encode(frame):
                            # Escribir el frame de audio re-codificado en el contenedor de salida
                            output_container.mux(packet)

                # Finalizar la codificación para asegurar que no queden frames pendientes
                for packet in output_stream.encode():
                    output_container.mux(packet)

        container.close()
        output_container.close()

    def ffmpeg_audio_download(self, url, output_file):
        streams = streamlink.streams(url)
        stream = streams["audio"]
        playlist_url = stream.url
        print(f"Downloading from {playlist_url}")
        # Ejecutar con subprocess
        import subprocess
        subprocess.run(["ffmpeg", "-i", playlist_url, "-ac", "1", "-ar", "16000", 
                        "-ss", "00:09:50",
                        "-y", "-acodec", "copy", 
                        output_file], check=True)

    # Convertir el video a audio usando moviepy
    def video_to_audio(self, video_path, audio_path):
        video_clip = VideoFileClip(video_path)
        audio_clip = video_clip.audio
        audio_clip.write_audiofile(audio_path)
        audio_clip.close()
        video_clip.close()

    def transcribe(self, audio_path):
        # Cargar el modelo Whisper
        model = whisper.load_model("medium")

        # Transcribir el audio con Whisper
        transcription = whisper.transcribe(model, audio_path, language="es", verbose=True)
        with open('transcription.json', 'w') as f:
            json.dump(transcription, f)

        return transcription
 
    def _summarize(self, text, username):
        response = client.chat.completions.create(
            model="Qwen/Qwen2-7B-Instruct-GGUF",
            messages=[
                {"role": "system",
                "content": """Te llamas Verónica. Eres un experto en resúmenes concisos de transcripciones de directos de Twitch.
                Haces resumenes breves pero informativos y sabes seleccionar los mejores momentos.
                Ignoras los saludos y bienvenidas a usuarios y te centras en los momentos más interesantes del directo.
                Nunca superas las 200 palabras en el resumen.
                Piensas cada frase paso a paso, vigilando que no superas la extensión máxima."""},
                {"role": "user",
                "content": f"""Haz un resumen de los mejores momentos de la siguiente transcripción de un directo de Twitch del canal de {username}.
                El resumen empezará siempre por "En el último episodio" y hablará del streamer y del directo de forma épica y entretenida, seleccionando los mejores momentos (excepto los saludos) .
                Es muy importante que ignores en el resumen todas las bienvenidas, saludos y despedidas y nunca los menciones. No incluyas las bienvenidas a usuarios en el resumen.
                No es necesario comentar en el resumen cuando se guardan partidas.
                Si escuchas la frase "Verónica, recuerda esto", debes incluir la información que se menciona a continuación en el resumen.
                Debes resaltar al menos 2 momentos importantes del directo.
                Debe terminar con una conclusión y animando al próximo directo.
                El resumen ha de ser conciso y no debe superar las 300 palabras.
                Este es el texto a resumir:\n\n{text}"""}
            ],
            temperature=0.4,
            )
        return response.choices[0].message.content
    
    def _join_summaries(self, summaries):
        text = ""
        for summary in summaries:
            text += summary + "\n***\n"
        response = client.chat.completions.create(
            model="Qwen/Qwen2-7B-Instruct-GGUF",
            messages=[
                {"role": "system",
                "content": """Eres un experto en unir resumenes de un mismo capítulo.
                Sabes unir resumenes de diferentes partes de un mismo texto para crear un resumen completo y coherente.
                Cada parte está separada por tres asteriscos y un salto de línea.
                Piensas cada frase paso a paso y procuras que la unión quede natural, sin que parezca que has
                unido partes del mismo directo de Twitch."""},
                {"role": "user",
                "content": f"""Une los resúmenes de diferentes partes de un directo de Twitch a partir del siguiente texto:\n\n{text}"""}
            ],
            temperature=0.4,
            )
        return response.choices[0].message.content

    # Resumir el texto
    def summarize_text(self, text, username):
        
        if len(text) > 32767:
            #divide the text in chunks of 32767 characters
            chunks = [text[i:i+32767] for i in range(0, len(text), 32767)]
            resumenes = []
            for chunk in chunks:
                resumenes.append(self._summarize(chunk, username))
            resumen_largo = self._join_summaries(resumenes)
        else:
            resumen_largo = self._summarize(text, username)

        # Resumir el resumen
        response = client.chat.completions.create(
            model="Qwen/Qwen2-7B-Instruct-GGUF",
            messages=[
                {"role": "system",
                "content": """Eres un experto en resúmenes concisos. Nunca superas los 500 caracteres en el resumen.
                Piensas cada frase paso a paso, vigilando que no superas la extensión máxima."""},
                {"role": "user",
                "content": f"""Haz un resumen en menos de 500 caracteres del siguiente texto:\n\n{resumen_largo}"""}
            ],
            temperature=0.4,
            )

        resumen_corto = response.choices[0].message.content

        # Hacer que el resumen largo no tenga lineas de mas de 80 caracteres, para que sea más legible
        resumen_largo = self.format_to_80_columns(resumen_largo)
        return resumen_largo, resumen_corto

    def format_to_80_columns(self, resumen_largo):
        rl = ""
        for line in resumen_largo.split('\n'):
            if line == '':
                continue
            if len(line) > 80:
                words = line.split(' ')
                new_line = ''
                while len(words) > 0:
                    word = words.pop(0)
                    if len(new_line) + len(word) <= 80:
                        new_line += word + ' '
                    else:
                        rl += new_line + '\n'
                        new_line = word + ' '
                rl += new_line + '\n'
            else:
                rl += line + '\n'
        resumen_largo = rl
        return resumen_largo
    
    def create_gist(self, content):
        url = 'https://api.github.com/gists'
        headers = {
            'Authorization': f'token {os.getenv("GITHUB_TOKEN")}'
        }
        data = {
            "description": "Resumen del último directo de Twitch",
            "public": True,
            "files": {
                "summary.txt": {
                    "content": content
                }
            }
        }
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        return response_data['html_url']
    


if __name__ == "__main__":
    username = 'drpalanca'
    recap = Recap(username, client, client_id, client_secret)

    last_stream = recap.get_last_stream()
    video_id = last_stream['id']
    print(f"Último directo ID: {video_id}")
    #video_id = 2177073636

    m3u8_url = recap.get_m3u8_url(video_id)
    print(f"URL del archivo .m3u8: {m3u8_url}")
    
    # Nombre del archivo de salida
    audio_path = 'twitch_audio.wav'

    with open('history.json', 'r') as history_fd:
        history = json.load(history_fd)

    if history["last"] != video_id:
        history["last"] = video_id
        history["historic"][video_id] = {
            "date": datetime.datetime.now().isoformat(),
            "transcription": "",
            "summary_short": "",
            "summary_long": ""
        }
        recap.ffmpeg_audio_download(m3u8_url, audio_path)
    
    if history["historic"][video_id]["transcription"] == "":
        transcription = recap.transcribe(audio_path)
        history["historic"][video_id]["transcription"] = transcription["text"]

    with open('transcription.json') as f:
        transcription = json.load(f)

    summary_long, summary_short = recap.summarize_text(transcription["text"], username)
    print(summary_long)
    print("====================================")
    print(summary_short)

    history["historic"][video_id]["summary_short"] = summary_short
    history["historic"][video_id]["summary_long"] = summary_long
    with open('history.json', 'w') as history_fd:
        json.dump(history, history_fd)

    # Crea un public gist en GitHub con el resumen y dame la url
    url = recap.create_gist(summary_long)
    print(f"Resumen: {url}")

    with open('summary.txt', 'w') as f:
        f.write(summary_short)
        f.write(f"\n\n Resumen completo: {url}")

