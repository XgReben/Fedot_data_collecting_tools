Wirenboard Data Aggregator Service
Сервис для сбора и обработки данных с ESP32

🔧 Требования
Wirenboard 7 (или другой ПЛК с Python 3.7+)
Доступ к MQTT брокеру

После запуска сервис будет доступен по адресу ПЛК http://<WB_IP>:8000

📡 API Endpoints
Endpoint	Метод	Описание	Пример ответа
/averages	GET	Средние значения последней выборки	#%D0%BF%D1%80%D0%B8%D0%BC%D0%B5%D1%80-%D0%BE%D1%82%D0%B2%D0%B5%D1%82%D0%B0-averages
/samples	GET	Все сохраненные семплы	#%D0%BF%D1%80%D0%B8%D0%BC%D0%B5%D1%80-%D0%BE%D1%82%D0%B2%D0%B5%D1%82%D0%B0-samples
/metadata	GET	Метаданные последней выборки	#%D0%BF%D1%80%D0%B8%D0%BC%D0%B5%D1%80-%D0%BE%D1%82%D0%B2%D0%B5%D1%82%D0%B0-metadata
/last_sample	GET	Последняя полная выборка	#%D0%BF%D1%80%D0%B8%D0%BC%D0%B5%D1%80-%D0%BE%D1%82%D0%B2%D0%B5%D1%82%D0%B0-last_sample

Примеры ответов:
/averages
{
  "current_avg": 123.45,
  "mic_avg": 456.78,
  "vibro_avg": 789.01,
  "timestamp": "2024-05-20T14:30:00Z"
}
/samples
{
  "samples": [
    {
      "values": [123, 125, 118, 450, 455, 460, 200, 205, 210],
      "timestamp": "2024-05-20T14:30:00Z",
      "sample_rate": 240000,
      "resolution": 12,
      "device_id": "ESP32-ABCD1234"
    }
  ]
}
/metadata
{
  "timestamp": "2024-05-20T14:30:00Z",
  "sample_rate": 240000,
  "resolution": 12,
  "device_id": "ESP32-ABCD1234"
}

Сервис ожидает данные от ESP32 в формате:

{
  "current": [значения],
  "mic": [значения],
  "vibro": [значения],
  "metadata": {
    "sample_rate": 240000,
    "resolution": 12,
    "timestamp": "ISO-8601",
    "device_id": "строка"
  }
}

ESP32 должна публиковать в MQTT:

URL → http://<IP_ESP32>/get_data
Data → 1 (флаг готовности данных)

⚡ Автозапуск
Вариант 1: systemd (рекомендуется)
Создайте файл сервиса:
sudo nano /etc/systemd/system/wb-data-aggregator.service
Добавьте конфигурацию:
[Unit]
Description=Wirenboard Data Aggregator Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/main.py
WorkingDirectory=/path/to/
Restart=always
User=root

[Install]
WantedBy=multi-user.target
Включите сервис:
sudo systemctl daemon-reload
sudo systemctl enable wb-data-aggregator
sudo systemctl start wb-data-aggregator
Вариант 2: crontab
Добавьте в crontab:

@reboot /usr/bin/python3 /path/to/main.py >> /var/log/wb-data-aggregator.log 2>&1