import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from fedot.core.pipelines.pipeline import Pipeline
from fedot.core.pipelines.node import PrimaryNode, SecondaryNode
from fedot.core.data.data import InputData
from fedot.core.data.data_split import train_test_data_setup
from fedot.core.repository.dataset_types import DataTypesEnum
from fedot.core.repository.tasks import Task, TaskTypesEnum
from fedot.industrial.data.data_split import industrial_validation_split
from fedot.industrial.pipelines.ts_classification_pipelines import ts_classification_pipeline
from fedot.industrial.utils.utils import ensure_directory_exists

class DataPreprocessor:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.data_dir = self.config.get('data_dir', 'data')
        self.labels_file = self.config.get('labels_file', 'labels.json')
        self.processed_dir = os.path.join(self.data_dir, 'processed')
        ensure_directory_exists(self.processed_dir)
        
    def load_config(self, config_path):
        """Загрузка конфигурационного файла"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def load_labels(self):
        """Загрузка меток классов"""
        labels_path = os.path.join(self.data_dir, self.labels_file)
        if os.path.exists(labels_path):
            with open(labels_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save_labels(self, labels):
        """Сохранение меток классов"""
        labels_path = os.path.join(self.data_dir, self.labels_file)
        with open(labels_path, 'w') as f:
            json.dump(labels, f, indent=4)
    
    def preprocess_samples(self):
        """Предварительная обработка семплов и создание единого датасета"""
        samples_dir = os.path.join(self.data_dir, 'samples')
        all_samples = []
        labels = self.load_labels()
        
        for sample_file in os.listdir(samples_dir):
            if sample_file.startswith('sample_') and sample_file.endswith('.csv'):
                file_path = os.path.join(samples_dir, sample_file)
                df = pd.read_csv(file_path)
                
                # Извлечение временных меток
                if 'exact_timestamp' in df.columns:
                    timestamps = pd.to_datetime(df['exact_timestamp'])
                elif 'timestamp' in df.columns:
                    timestamps = pd.to_datetime(df['timestamp'])
                else:
                    timestamps = pd.Series([datetime.now()] * len(df))
                
                # Извлечение значений
                values = df['values'].values if 'values' in df.columns else df['current_avg'].values
                
                # Создание фичей (можно добавить дополнительные)
                features = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'max': np.max(values),
                    'min': np.min(values),
                    # Добавьте другие статистики по необходимости
                }
                
                # Определение метки класса (если есть)
                sample_id = sample_file.replace('.csv', '')
                label = labels.get(sample_id, -1)  # -1 для неразмеченных данных
                
                all_samples.append({
                    'sample_id': sample_id,
                    'timestamps': timestamps,
                    'values': values,
                    'features': features,
                    'label': label
                })
        
        # Сохранение обработанных данных
        processed_path = os.path.join(self.processed_dir, 'processed_data.json')
        with open(processed_path, 'w') as f:
            json.dump(all_samples, f, indent=4)
        
        return all_samples

class TSClassifierTrainer:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.data_dir = self.config.get('data_dir', 'data')
        self.processed_dir = os.path.join(self.data_dir, 'processed')
        self.models_dir = os.path.join(self.data_dir, 'models')
        ensure_directory_exists(self.models_dir)
        
    def load_config(self, config_path):
        """Загрузка конфигурационного файла"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def prepare_input_data(self, samples):
        """Подготовка данных для FEDOT"""
        # Преобразование в numpy массивы
        features = np.array([[s['features']['mean'], 
                             s['features']['std'],
                             s['features']['max'],
                             s['features']['min']] for s in samples])
        
        labels = np.array([s['label'] for s in samples])
        
        # Создание объекта InputData для FEDOT
        task = Task(TaskTypesEnum.classification)
        input_data = InputData(
            idx=np.arange(len(samples)),
            features=features,
            target=labels,
            task=task,
            data_type=DataTypesEnum.table
        )
        
        return input_data
    
    def create_pipeline(self):
        """Создание пайплайна для классификации временных рядов"""
        # Простой пайплайн для начала (можно усложнить)
        node_scaling = PrimaryNode('scaling')
        node_pca = SecondaryNode('pca', nodes_from=[node_scaling])
        node_rf = SecondaryNode('rf', nodes_from=[node_pca])
        
        pipeline = Pipeline(node_rf)
        return pipeline
    
    def train_classifier(self, samples):
        """Обучение классификатора"""
        # Подготовка данных
        input_data = self.prepare_input_data(samples)
        
        # Разделение на train/test
        train_data, test_data = train_test_data_setup(input_data)
        
        # Создание и обучение пайплайна
        pipeline = self.create_pipeline()
        pipeline.fit(train_data)
        
        # Оценка качества
        predicted = pipeline.predict(test_data)
        true_labels = test_data.target
        
        accuracy = np.mean(predicted.predict == true_labels)
        print(f"Accuracy: {accuracy:.2f}")
        
        # Сохранение модели
        model_path = os.path.join(self.models_dir, 'ts_classifier')
        pipeline.save(model_path)
        print(f"Model saved to {model_path}")
        
        return pipeline

def main():
    # 1. Предварительная обработка данных
    preprocessor = DataPreprocessor()
    samples = preprocessor.preprocess_samples()
    
    # Проверка наличия размеченных данных
    labeled_samples = [s for s in samples if s['label'] != -1]
    if len(labeled_samples) == 0:
        print("No labeled samples found. Please label your data first.")
        return
    
    # 2. Обучение классификатора
    trainer = TSClassifierTrainer()
    pipeline = trainer.train_classifier(labeled_samples)
    
    print("Training completed successfully!")

if __name__ == "__main__":
    main()