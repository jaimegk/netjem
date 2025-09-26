FROM python:3.13-slim

WORKDIR /app

# Instalar herramientas de compilación, tc y libpcap
RUN apt-get update && apt-get install -y \
    gcc \
    libc6-dev \
    iproute2 \
    libpcap0.8 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 11111

CMD ["python", "-m", "uvicorn", "NetJemAPI:app", "--host", "0.0.0.0", "--port", "11111"]