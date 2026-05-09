# Python 3.11 image dan foydalanamiz
FROM python:3.11-slim

# Tizim paketlarini yangilash va ffmpeg, nodejs o'rnatish
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    python3-pip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Ishchi katalogni belgilash
WORKDIR /app

# Kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllarini ko'chirish
COPY . .

# Botni ishga tushirish
CMD ["python", "bot.py"]
