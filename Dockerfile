FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Zavisimostu Python (psycopg2-binary — gotovy binarny paket, ne trebuet kompilacii)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sozdaem neobhodimye direktorii
RUN mkdir -p logs staticfiles media

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

ENTRYPOINT ["sh", "/entrypoint.sh"]
