FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Application code, research package, immutable input copies, and generated
# dashboard artifacts. Raw per-tick JSONL files are excluded in .dockerignore.
COPY app.py controller.py ./
COPY eaes ./eaes
COPY configs ./configs
COPY data ./data
COPY results ./results
COPY templates ./templates
COPY static ./static

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "app.py"]
