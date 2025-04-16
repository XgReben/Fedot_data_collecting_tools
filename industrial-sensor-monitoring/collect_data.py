import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os
import json
from scipy import interpolate
import configparser

class APIDataCollector:
    def __init__(self, config_file='config.ini'):
        # Загрузка конфигурации
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Параметры API
        self.base_url = self.config.get('API', 'base_url', fallback='http://localhost:8000')
        self.endpoints = {
            'averages': '/averages',
            'samples': '/samples',
            'metadata': '/metadata',
            'last_sample': '/last_sample'
        }
        
        # Параметры сбора данных
        self.sample_size = self.config.getint('Data', 'sample_size', fallback=100)
        self.collection_interval = self.config.getint('Data', 'collection_interval', fallback=60)
        self.output_dir = self.config.get('Data', 'output_dir', fallback='data')
        self.samples_dir = os.path.join(self.output_dir, 'samples')
        self.merged_file = os.path.join(self.output_dir, 'merged_data.csv')
        
        # Создание директорий, если они не существуют
        os.makedirs(self.samples_dir, exist_ok=True)
        
        # Инициализация переменных для хранения данных
        self.merged_data = pd.DataFrame()
        self.last_timestamp = None
        
    def get_api_data(self, endpoint):
        """Получение данных из API"""
        url = self.base_url + self.endpoints[endpoint]
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к {url}: {e}")
            return None
    
    def save_sample_to_csv(self, data, filename=None):
        """Сохранение выборки в CSV файл"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"sample_{timestamp}.csv"
        
        filepath = os.path.join(self.samples_dir, filename)
        df = pd.DataFrame(data['samples'])
        df.to_csv(filepath, index=False)
        print(f"Сохранено: {filepath}")
        return filepath
    
    def collect_samples(self):
        """Сбор заданного количества выборок"""
        samples_collected = 0
        sample_files = []
        
        while samples_collected < self.sample_size:
            data = self.get_api_data('samples')
            if data and 'samples' in data:
                sample_file = self.save_sample_to_csv(data)
                sample_files.append(sample_file)
                samples_collected += len(data['samples'])
            
            time.sleep(self.collection_interval)
        
        return sample_files
    
    def merge_samples(self, sample_files=None):
        """Объединение выборок в единый временной ряд"""
        if sample_files is None:
            sample_files = [os.path.join(self.samples_dir, f) for f in os.listdir(self.samples_dir) 
                          if f.startswith('sample_') and f.endswith('.csv')]
        
        all_data = []
        
        for file in sample_files:
            try:
                df = pd.read_csv(file)
                # Преобразование данных из списков в отдельные строки
                df_exploded = df.explode('values')
                df_exploded['timestamp'] = pd.to_datetime(df_exploded['timestamp'])
                
                # Рассчет временных меток для каждого значения в выборке
                sample_rate = df_exploded['sample_rate'].iloc[0]
                time_delta = 1 / sample_rate
                
                # Создание временных меток для каждого значения
                timestamps = []
                for _, group in df_exploded.groupby('timestamp'):
                    start_time = group['timestamp'].iloc[0]
                    times = [start_time + timedelta(seconds=i*time_delta) for i in range(len(group))]
                    timestamps.extend(times)
                
                df_exploded['exact_timestamp'] = timestamps
                all_data.append(df_exploded)
            except Exception as e:
                print(f"Ошибка при обработке файла {file}: {e}")
        
        if not all_data:
            print("Нет данных для объединения")
            return
        
        merged = pd.concat(all_data).sort_values('exact_timestamp')
        
        # Удаление дубликатов (если есть)
        merged = merged.drop_duplicates(subset=['exact_timestamp', 'device_id'], keep='last')
        
        # Сохранение объединенных данных
        merged.to_csv(self.merged_file, index=False)
        print(f"Объединенные данные сохранены в {self.merged_file}")
        
        self.merged_data = merged
        return merged
    
    def fill_missing_data(self, resample_freq='1S', method='linear'):
        """Заполнение пропущенных данных с помощью аппроксимации"""
        if self.merged_data.empty:
            print("Нет данных для обработки. Сначала выполните объединение выборок.")
            return None
        
        # Создание регулярного временного ряда
        min_time = self.merged_data['exact_timestamp'].min()
        max_time = self.merged_data['exact_timestamp'].max()
        full_range = pd.date_range(start=min_time, end=max_time, freq=resample_freq)
        
        # Подготовка данных для интерполяции
        timestamps = self.merged_data['exact_timestamp'].values.astype(np.int64) // 10**9
        values = self.merged_data['values'].values
        
        # Создание функции интерполяции
        interp_func = interpolate.interp1d(
            timestamps, 
            values, 
            kind=method, 
            fill_value='extrapolate'
        )
        
        # Применение интерполяции
        full_timestamps = full_range.values.astype(np.int64) // 10**9
        interpolated_values = interp_func(full_timestamps)
        
        # Создание DataFrame с заполненными данными
        filled_data = pd.DataFrame({
            'timestamp': full_range,
            'values': interpolated_values
        })
        
        # Добавление метаданных (берем из последней записи)
        for col in ['sample_rate', 'resolution', 'device_id']:
            if col in self.merged_data.columns:
                filled_data[col] = self.merged_data[col].iloc[0]
        
        # Сохранение результатов
        filled_file = os.path.join(self.output_dir, 'filled_data.csv')
        filled_data.to_csv(filled_file, index=False)
        print(f"Данные с заполненными пропусками сохранены в {filled_file}")
        
        return filled_data
    
    def run(self):
        """Основной цикл сбора и обработки данных"""
        print("Начало сбора данных...")
        try:
            while True:
                # Сбор выборок
                sample_files = self.collect_samples()
                
                # Объединение данных
                merged_data = self.merge_samples(sample_files)
                
                # Заполнение пропусков
                if merged_data is not None:
                    self.fill_missing_data()
                
                print(f"Ожидание следующего цикла сбора ({self.collection_interval} сек)...")
                time.sleep(self.collection_interval)
                
        except KeyboardInterrupt:
            print("Сбор данных остановлен пользователем")


if __name__ == "__main__":
    # Создание конфигурационного файла, если его нет
    if not os.path.exists('config.ini'):
        config = configparser.ConfigParser()
        config['API'] = {
            'base_url': 'http://localhost:8000'
        }
        config['Data'] = {
            'sample_size': '100',
            'collection_interval': '60',
            'output_dir': 'data'
        }
        
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
        print("Создан конфигурационный файл config.ini")
    
    # Запуск сборщика данных
    collector = APIDataCollector()
    collector.run()