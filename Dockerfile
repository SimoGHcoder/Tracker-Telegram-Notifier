FROM python:3.11-alpine

WORKDIR /app

# Installazione dipendenze di sistema
RUN apk add --no-cache gcc musl-dev tzdata

# Copia e installazione dei requisiti Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia codice sorgente
COPY . .

# Creazione cartella per i dati persistenti
RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
