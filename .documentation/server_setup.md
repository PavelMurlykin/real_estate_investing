# Настройка сервера

Документ описывает разовую подготовку чистого сервера Ubuntu 24 LTS для запуска
проекта `real_estate_investing` в Docker Compose.

## Что будет настроено

- подключение к серверу по SSH;
- обновление ОС и установка базовых пакетов;
- firewall через `ufw`;
- Docker Engine и Docker Compose plugin;
- доступ сервера к GitHub по SSH;
- директории для приложений и backup-файлов.

## Подключение к серверу

Команда выполняется на локальной машине Windows в PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\rpi5-server" pavelmurlykin@192.168.1.95
```

Если используется SSH-ключ по умолчанию:

```powershell
ssh pavelmurlykin@192.168.1.95
```

Дальнейшие команды выполняются на сервере, если явно не указано иное.

## Обновление ОС и базовые пакеты

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y git curl ca-certificates nano ufw htop openssh-server
sudo systemctl enable --now ssh
sudo reboot
```

После перезагрузки снова подключиться по SSH.

## Настройка firewall

Открыть SSH, HTTP и HTTPS:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

PostgreSQL не нужно открывать наружу. В проекте он доступен только внутри
Docker-сети.

## Установка Docker Engine

Добавить официальный Docker repository:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Установить Docker и Compose plugin:

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Добавить текущего пользователя в группу `docker`:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

Проверить установку:

```bash
docker version
docker compose version
```

Включить Docker при старте ОС:

```bash
sudo systemctl enable docker
```

## Настройка SSH-доступа сервера к GitHub

Сгенерировать SSH-ключ на сервере:

```bash
ssh-keygen -t ed25519 -C "rpi5-server"
```

Можно оставить путь по умолчанию:

```text
/home/pavelmurlykin/.ssh/id_ed25519
```

Показать публичный ключ:

```bash
cat ~/.ssh/id_ed25519.pub
```

Добавить этот ключ в GitHub:

```text
GitHub -> Settings -> SSH and GPG keys -> New SSH key
```

Проверить доступ:

```bash
ssh -T git@github.com
```

При первом подключении подтвердить fingerprint GitHub, если он выглядит
ожидаемо. После успешной проверки GitHub ответит, что аутентификация прошла,
но shell-доступ не предоставляется. Это нормальное поведение.

## Рабочие директории

Создать папки для приложений и backup-файлов:

```bash
mkdir -p ~/apps
mkdir -p ~/backups
```

Рекомендуется хранить PostgreSQL volume на SSD, если сервер работает с
постоянной нагрузкой. MicroSD подходит для экспериментов, но хуже переносит
частые записи базы данных.

## Проверка готовности сервера

```bash
git --version
docker version
docker compose version
sudo ufw status
ssh -T git@github.com
```

После этой настройки переходить к
`.documentation/application_initial_setup.md`.

После первичного запуска приложения можно настроить HTTPS по
`.documentation/https_setup.md`.
