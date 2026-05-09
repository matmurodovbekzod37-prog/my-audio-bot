FROM python:3.11-slim

# Tizim paketlarini (ffmpeg va nodejs) o'rnatish
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Portni ochish (Render uchun)
EXPOSE 10000

CMD ["python", "bot.py"]
