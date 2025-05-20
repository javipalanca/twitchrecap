FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias de sistema
RUN apt-get update && apt-get install -y \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar los archivos del proyecto
COPY requirements.txt .
COPY *.py .
COPY .env .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Configuración de variables de entorno
ENV PYTHONUNBUFFERED=1

# Puerto para exposición si es necesario
# EXPOSE 8000

# Script de inicio que ejecuta ambos bots
RUN echo '#!/bin/bash\n\
python bot.py & \
python discordbot.py & \
wait' > /app/start.sh

RUN chmod +x /app/start.sh

# Ejecutar el script de inicio
CMD ["/app/start.sh"]