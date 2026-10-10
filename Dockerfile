FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Порт для Hugging Face Spaces (по умолчанию 7860)
ENV PORT=7860
EXPOSE 7860

CMD ["python", "main.py"]
