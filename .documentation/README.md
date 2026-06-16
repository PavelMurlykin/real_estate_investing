# Документация эксплуатации

Карта документов для ручной эксплуатации проекта `real_estate_investing`.

## Разовые процессы

- `server_setup.md` - подготовка чистого сервера: SSH, firewall, Docker,
  Docker Compose, SSH-доступ к GitHub.
- `application_initial_setup.md` - первичная настройка приложения: clone
  репозитория, `.env`, первый запуск контейнеров, восстановление базы,
  автозапуск через systemd.
- `https_setup.md` - подключение HTTPS через Caddy перед текущим Docker Compose
  nginx.

## Регулярные процессы

- `manual_deployment.md` - ручной деплой после изменений в Git.
- `production_update_checklist.md` - краткий checklist перед production
  обновлением.
- `backup_restore.md` - создание, проверка и восстановление backup PostgreSQL.
- `role_model.md` - роли пользователей, матрица доступа и backend-контракт
  проверок прав.

## Диагностика

- `troubleshooting.md` - типовые ошибки и способы их исправления.

## Рекомендуемый порядок чтения при первом запуске

1. `server_setup.md`
2. `application_initial_setup.md`
3. `backup_restore.md`, если нужно перенести существующую базу
4. `https_setup.md`, если есть домен и нужен HTTPS
5. `manual_deployment.md` для последующих обновлений
