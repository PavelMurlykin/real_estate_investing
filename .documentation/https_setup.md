# HTTPS для приложения

Документ описывает рекомендуемый способ включить HTTPS для текущего проекта:
оставить Docker Compose stack как внутреннее приложение на порту `8080`, а
перед ним поставить Caddy на хосте. Caddy будет слушать `80` и `443`, получать
сертификаты Let's Encrypt и проксировать запросы в nginx проекта.

## Предпосылки

- Есть домен, например `example.com`.
- DNS A-record домена указывает на публичный IP сервера.
- На роутере проброшены порты `80` и `443` на Raspberry Pi.
- В firewall открыты `80/tcp` и `443/tcp`.

Проверить firewall:

```bash
sudo ufw status
```

## Настройка приложения на внутренний порт

В `.env` проекта указать:

```env
NGINX_PORT=8080
ALLOWED_HOSTS=localhost,127.0.0.1,web,example.com
CSRF_TRUSTED_ORIGINS=https://example.com
```

Перезапустить приложение:

```bash
cd ~/apps/real_estate_investing
docker compose up -d --force-recreate
```

Проверить локально на сервере:

```bash
curl -I http://127.0.0.1:8080/health/
```

## Установка Caddy

Попробовать установить Caddy из пакетов Ubuntu:

```bash
sudo apt update
sudo apt install -y caddy
```

Если пакета нет или нужна более свежая версия, использовать официальный способ
установки из документации Caddy.

Проверить service:

```bash
systemctl status caddy
```

## Конфигурация Caddy

Открыть конфиг:

```bash
sudo nano /etc/caddy/Caddyfile
```

Минимальный вариант:

```caddyfile
example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Проверить конфигурацию:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
```

Перезагрузить Caddy:

```bash
sudo systemctl reload caddy
```

Открыть приложение:

```text
https://example.com/
```

## Проверка сертификата и прокси

```bash
curl -I https://example.com/health/
sudo journalctl -u caddy --no-pager -n 100
```

Если сертификат не выдается, проверить:

- DNS домена указывает на сервер;
- порты `80` и `443` доступны извне;
- на этих портах не работает другой сервис;
- `NGINX_PORT` приложения не занимает `80`;
- в логах Caddy нет ошибок ACME.

## Важные замечания

Не запускать одновременно Caddy и Compose nginx на host-порту `80`. Для схемы с
Caddy приложение должно быть доступно на внутреннем host-порту `8080`, а Caddy
должен слушать `80` и `443`.

PostgreSQL не должен публиковаться наружу ни при HTTP, ни при HTTPS.

Если позже будет добавлен HTTPS прямо в Docker Compose nginx, эту инструкцию
нужно пересмотреть и убрать Caddy или изменить портовую схему.
