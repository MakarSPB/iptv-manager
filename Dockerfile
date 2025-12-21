FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем необходимые директории
RUN mkdir -p /app/data /app/uploads

# Открываем порт
EXPOSE 8000

# Запускаем приложение
CMD ["python", "main.py"]