FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём необходимые директории
RUN mkdir -p /app/data /app/uploads

# Экспорт порта (не влияет на запуск, но документирует)
EXPOSE 8024

# Запускаем через main.py — чтобы использовать настройки из config.py
CMD ["python", "main.py"]