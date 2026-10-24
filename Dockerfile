FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --uid 1000 --create-home botuser
USER botuser

CMD ["python", "main.py"]
