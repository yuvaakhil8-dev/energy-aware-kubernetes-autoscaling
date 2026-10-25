FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Application code plus the modules/assets required by the dashboard and controller.
COPY app.py controller.py ./
COPY templates ./templates
COPY static ./static

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "app.py"]
