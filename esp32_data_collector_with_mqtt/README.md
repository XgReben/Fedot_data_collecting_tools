# Fedot_data_collecting_tools
Utilities for collecting and prigessing data on edge device for Fedot.Industrial and frdcore frameworks

Проект сбора данных с датчиков через ESP32 и интеграции с Fedot.Industrial

Этот проект предназначен для сбора данных с промышленных датчиков (ток, микрофон, вибрация) с использованием ESP32, передачи их по WiFi в MQTT-брокер (Wirenboard 7) и последующей обработки в Python для преобразования в формат InputData фреймворка https://github.com/aimclub/Fedot.Industrial.

🔌 Подключение датчиков к ESP32
ESP32 считывает данные с трех аналоговых датчиков:

Токовый датчик (CUR_SENSE_0) → GPIO 32
Микрофон (MIC_SENSE_0) → GPIO 33
Датчик вибрации (VIBRO_SENSE_0) → GPIO 35
Схема подключения
Датчик	GPIO ESP32	Примечание
Токовый датчик	32	Подключен через резистор 100 Ом
Микрофон	33	Аналоговый микрофонный модуль
Датчик вибрации	35	Пьезоэлектрический сенсор
📌 Дополнительные настройки:

АЦП работает в режиме DMA (непрерывное чтение).
Частота дискретизации: 240 кГц.
Разрешение АЦП: 12 бит.
📶 Настройка WiFi и MQTT
ESP32 подключается к Wirenboard 7 по WiFi и отправляет данные в MQTT.

Конфигурация сети
const char* ssid = "Wirenboard";  
const char* password = "Wirenboard";  
const char* mqttServer = "192.168.0.67";  
const int mqttPort = 1883;  
const char* mqttUser = "Fedot_collector_ADC";  
const char* mqttPassword = без пароля

Отправляемые MQTT-сообщения
Топик	Данные	Описание
URL	http://<IP_ESP32>/get_data	URL для скачивания данных через HTTP
Data	0 (нет данных) / 1 (есть)	Флаг готовности данных

📌 Как это работает?

ESP32 подключается к WiFi и MQTT.
Отправляет свой URL (http://<IP_ESP32>/get_data).
Когда данные готовы (data_ready = 1), по запросу http://<IP_ESP32>/get_data доступны данные с датчиков в формате json

После сбора данных с датчиков (ток, микрофон, вибрация) ESP32 формирует JSON-пакет следующей структуры:

{
  "current": [123, 125, 118, 120, 122, ...],
  "mic": [450, 455, 460, 452, 448, ...],
  "vibro": [200, 205, 210, 208, 203, ...],
  "metadata": {
    "sample_rate": 240000,
    "resolution": 12,
    "timestamp": "2024-05-20T14:30:00Z",
    "device_id": "ESP32-ABCD1234"
  }
}

Разбор полей:
current (array[int]):
Аналоговые значения с токового датчика (GPIO 32).
Пример: [123, 125, 118, ...] (12-битные значения, 0–4095).
mic (array[int]):
Данные с микрофона (GPIO 33).
Пример: [450, 455, 460, ...].
vibro (array[int]):
Показания вибродатчика (GPIO 35).
Пример: [200, 205, 210, ...].
metadata (object):
sample_rate: Частота дискретизации (240 кГц). !!! Так как датчики мультиплексированые колличество выборок равно ЧД/колличество каналов
resolution: Разрешение АЦП (12 бит).
timestamp: Время сбора данных в ISO-формате.
device_id: Уникальный идентификатор ESP32 (MAC-адрес).

Пример HTTP-ответа от /get_data
При запросе GET http://<IP_ESP32>/get_data сервер возвращает:

HTTP/1.1 200 OK
Content-Type: application/json

{
  "current": [123, 125, 118, 120, 122, ...],
  "mic": [450, 455, 460, 452, 448, ...],
  "vibro": [200, 205, 210, 208, 203, ...],
  "metadata": {
    "sample_rate": 240000,
    "resolution": 12,
    "timestamp": "2024-05-20T14:30:00Z",
    "device_id": "ESP32-ABCD1234"
  }
}

Как обрабатывать эти данные в Python?
Скачивание через HTTP:
   import requests
   response = requests.get("http://192.168.0.100/get_data")
   data = response.json()  # Получаем JSON

Преобразование в InputData для Fedot.Industrial:
   from fedot.industrial.data import InputData

   input_data = InputData(
       features=[data["current"], data["mic"], data["vibro"]],
       target=None,  # Если нет меток
       task="regression"
   )