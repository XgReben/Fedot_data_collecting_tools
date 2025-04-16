Data Collection and Analysis System
Описание проекта
Это система для сбора, визуализации и классификации временных рядов данных, состоящая из трех основных компонентов:

Сбор данных - получение данных из API и сохранение в CSV файлы
Визуализация - веб-интерфейс для просмотра данных (осциллограммы, спектры)
Классификация - обучение модели и предсказание классов для семплов
Установка
Клонируйте репозиторий:
git clone <repository-url>
cd <repository-folder>
Установите зависимости:
pip install -r requirements.txt
Использование
1. Сбор данных
python data_collector.py
Конфигурация в файле config.ini:

[API]
base_url = http://your-api-url

[Data]
sample_size = 100
collection_interval = 60
output_dir = data
2. Генерация синтетических данных (опционально)
python generate_samples.py
Параметры генерации можно изменить в конце файла generate_samples.py.

3. Запуск веб-интерфейса
python app.py
Откройте в браузере: http://localhost:5000

Функционал веб-интерфейса:

Просмотр загруженных семплов
Визуализация (осциллограммы, Фурье-спектры, вейвлет-спектры)
Разметка данных (назначение классов)
Предсказание классов (если модель существует)
4. Обучение модели классификации
python train_classifier.py
Модель сохраняется в data/models/ts_classifier

Структура проекта
data/
  samples/          # Исходные семплы
  synthetic_samples/ # Сгенерированные семплы
  models/           # Обученные модели
  labels.json       # Метки классов
templates/
  index.html        # Веб-интерфейс
app.py              # Веб-приложение
data_collector.py   # Сбор данных
train_classifier.py # Обучение модели
generate_samples.py # Генерация данных
config.ini          # Конфигурация
requirements.txt    # Зависимости
Настройка
Для работы с API укажите правильный base_url в config.ini
Для изменения параметров визуализации редактируйте app.py
Для настройки модели редактируйте train_classifier.py