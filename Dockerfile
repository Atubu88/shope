FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект (код + базу данных)
COPY . .

# Для логов (по желанию)
ENV PYTHONUNBUFFERED=1

# Запуск твоего основного скрипта
CMD ["python", "main.py"]
