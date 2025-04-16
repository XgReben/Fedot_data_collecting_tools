import numpy as np
import pandas as pd
import os
from datetime import datetime, timedelta
import json

def generate_synthetic_samples(num_samples=100, sample_rate=1000, duration=1, freq=50, noise_level=0.2):
    """
    Генерация синтетических семплов с зашумленной синусоидой
    
    Параметры:
    - num_samples: количество семплов для генерации
    - sample_rate: частота дискретизации (Гц)
    - duration: длительность семпла (сек)
    - freq: частота синусоиды (Гц)
    - noise_level: уровень шума (от 0 до 1)
    """
    # Создаем директорию для сохранения, если ее нет
    os.makedirs('data/synthetic_samples', exist_ok=True)
    
    # Метаданные для сохранения
    metadata = {
        'num_samples': num_samples,
        'sample_rate': sample_rate,
        'duration': duration,
        'base_frequency': freq,
        'noise_level': noise_level,
        'generated_at': datetime.now().isoformat()
    }
    
    # Генерируем временную ось
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    for i in range(num_samples):
        # Генерация синусоиды с небольшим случайным отклонением частоты
        current_freq = freq * (1 + 0.1 * np.random.randn())  # ±10% вариация частоты
        sine_wave = np.sin(2 * np.pi * current_freq * t)
        
        # Добавляем шум
        noise = noise_level * np.random.randn(len(t))
        signal = sine_wave + noise
        
        # Создаем временные метки
        start_time = datetime.now() - timedelta(days=num_samples - i)
        timestamps = [start_time + timedelta(seconds=dt) for dt in t]
        
        # Создаем DataFrame
        df = pd.DataFrame({
            'timestamp': timestamps,
            'values': signal,
            'sample_rate': sample_rate,
            'frequency': current_freq,
            'noise_level': noise_level
        })
        
        # Сохраняем в CSV
        filename = f"sample_{start_time.strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(f'data/synthetic_samples/{filename}', index=False)
    
    # Сохраняем метаданные
    with open('data/synthetic_samples/metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Сгенерировано {num_samples} семплов в папке data/synthetic_samples")

if __name__ == "__main__":
    # Генерация 100 семплов:
    # - Частота дискретизации 1000 Гц
    # - Длительность 1 секунда
    # - Основная частота 50 Гц
    # - Уровень шума 20%
    generate_synthetic_samples(
        num_samples=100,
        sample_rate=1000,
        duration=1,
        freq=50,
        noise_level=0.2
    )