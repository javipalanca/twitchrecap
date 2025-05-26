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

# Crear directorio templates
RUN mkdir -p templates

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Configuración de variables de entorno
ENV PYTHONUNBUFFERED=1
ENV ADMIN_USERNAME=admin
ENV ADMIN_PASSWORD=contraseña_segura

# Exponer el puerto para la interfaz web
EXPOSE 5555

# Script de inicio que ejecuta ambos bots y la interfaz web
RUN echo '#!/bin/bash\n\
python bot.py & \
python discordbot.py & \
python webcontrol.py & \
wait' > /app/start.sh

RUN chmod +x /app/start.sh

# Ejecutar el script de inicio
CMD ["/app/start.sh"]