FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# MG_RUCERT: корневые сертификаты НУЦ Минцифры. Российские сервисы (в т.ч.
# Bot API мессенджера Max) отдают TLS-сертификаты этого УЦ, которого нет в
# стандартном хранилище — без них запросы падают с CERTIFICATE_VERIFY_FAILED.
# Сборка не прерывается, если источник недоступен (напр. вне РФ): тогда
# просто не будет доступа к таким сервисам, остальное работает.
RUN set -eu; \
    ok=1; \
    for name in root sub; do \
        curl -fsSL --max-time 30 \
            "https://gu-st.ru/content/lending/russian_trusted_${name}_ca_pem.crt" \
            -o "/usr/local/share/ca-certificates/russian_trusted_${name}_ca.crt" || ok=0; \
    done; \
    if [ "$ok" = "1" ]; then \
        update-ca-certificates; \
        echo "MG_RUCERT: сертификаты Минцифры установлены"; \
    else \
        rm -f /usr/local/share/ca-certificates/russian_trusted_*_ca.crt; \
        echo "MG_RUCERT: ВНИМАНИЕ — сертификаты Минцифры не скачаны (нет доступа к gu-st.ru)"; \
    fi

# requests по умолчанию доверяет бандлу certifi, где российских УЦ нет.
# Переключаем на системный бандл: в нём и публичные CA, и добавленные выше.
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
