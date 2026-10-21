FROM php:8.3-apache
# zip — чтение .xlsx (это zip-архив с XML), pdo_mysql — доступ к БД
RUN apt-get update && apt-get install -y --no-install-recommends libzip-dev \
    && docker-php-ext-install pdo_mysql zip \
    && rm -rf /var/lib/apt/lists/*
# выписка за год весит несколько мегабайт
RUN printf 'upload_max_filesize=32M\npost_max_size=40M\nmemory_limit=512M\nmax_execution_time=180\n' \
    > /usr/local/etc/php/conf.d/uploads.ini
