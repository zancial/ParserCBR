Установка зависимостей - pip install -r app/requirements.txt

Запуск nats сервера - ./app/nats-server

Запуск nats клиента - ./app/nats

Запуск проекта - uvicorn app.main:app

Подключение по websocket - ws://localhost:8000/ws/currency

Адрес сервера - http://localhost:8000/

Swagger - http://localhost:8000/docs

Подписка на тему nats - ./app/nats sub currency.updates

Пример добавления записи в БД через nats - ./app/nats pub currency.updates '{\"char_code\": \"1234\", \"name\": \"2345\", \"value\": 1234}'
