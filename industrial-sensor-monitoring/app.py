import os
import json
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from fedot.core.pipelines.pipeline import Pipeline
from fedot.core.data.data import InputData
from fedot.core.repository.dataset_types import DataTypesEnum
from fedot.core.repository.tasks import Task, TaskTypesEnum
from werkzeug.utils import secure_filename
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from scipy.fft import fft, fftfreq
import pywt

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'data/samples'
app.config['LABELS_FILE'] = 'data/labels.json'
app.config['MODEL_FILE'] = 'data/models/ts_classifier'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def load_labels():
    if os.path.exists(app.config['LABELS_FILE']):
        with open(app.config['LABELS_FILE'], 'r') as f:
            return json.load(f)
    return {}

def save_labels(labels):
    with open(app.config['LABELS_FILE'], 'w') as f:
        json.dump(labels, f, indent=4)

def load_model():
    if os.path.exists(app.config['MODEL_FILE']):
        try:
            return Pipeline.load(app.config['MODEL_FILE'])
        except:
            return None
    return None

def get_samples():
    samples = []
    labels = load_labels()
    
    for f in os.listdir(app.config['UPLOAD_FOLDER']):
        if f.startswith('sample_') and f.endswith('.csv'):
            sample_id = f.replace('.csv', '')
            label = labels.get(sample_id, None)
            
            try:
                timestamp = datetime.strptime(f.replace('sample_', '').replace('.csv', ''), '%Y%m%d_%H%M%S')
                samples.append({
                    'id': sample_id,
                    'filename': f,
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'label': label
                })
            except:
                samples.append({
                    'id': sample_id,
                    'filename': f,
                    'timestamp': 'Unknown',
                    'label': label
                })
    
    return sorted(samples, key=lambda x: x['timestamp'], reverse=True)

def prepare_sample_for_prediction(filepath):
    df = pd.read_csv(filepath)
    values = df['values'].values if 'values' in df.columns else df['current_avg'].values
    
    features = np.array([[
        np.mean(values),
        np.std(values),
        np.max(values),
        np.min(values)
    ]])
    
    input_data = InputData(
        idx=np.array([0]),
        features=features,
        target=None,
        task=Task(TaskTypesEnum.classification),
        data_type=DataTypesEnum.table
    )
    
    return input_data

def create_plot(df, plot_type='oscillogram'):
    plt.figure(figsize=(10, 4))
    
    if plot_type == 'oscillogram':
        time_col = 'exact_timestamp' if 'exact_timestamp' in df.columns else 'timestamp'
        value_col = 'values' if 'values' in df.columns else 'current_avg'
        plt.plot(df[time_col], df[value_col])
        plt.title('Осциллограмма')
        plt.xlabel('Время')
        plt.ylabel('Амплитуда')
    
    elif plot_type == 'fft':
        values = df['values'].values if 'values' in df.columns else df['current_avg'].values
        n = len(values)
        yf = fft(values)
        xf = fftfreq(n, 1 / (df['sample_rate'].iloc[0] if 'sample_rate' in df.columns else 1000))
        plt.plot(xf[:n//2], np.abs(yf[:n//2]))
        plt.title('Фурье-спектр')
        plt.xlabel('Частота (Гц)')
        plt.ylabel('Амплитуда')
    
    elif plot_type == 'wavelet':
        values = df['values'].values if 'values' in df.columns else df['current_avg'].values
        scales = np.arange(1, 128)
        wavelet = 'cmor1.5-1.0'
        coefficients, _ = pywt.cwt(values, scales, wavelet, 
                                 sampling_period=1/(df['sample_rate'].iloc[0] if 'sample_rate' in df.columns else 1000))
        plt.imshow(np.abs(coefficients), extent=[0, len(values), 1, 128], 
                  cmap='jet', aspect='auto')
        plt.title('Вейвлет-спектр')
        plt.xlabel('Время (отсчеты)')
        plt.ylabel('Масштаб')
        plt.colorbar()
    
    plt.grid(True)
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    plt.close()
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

@app.route('/')
def index():
    samples = get_samples()
    model_exists = os.path.exists(app.config['MODEL_FILE'])
    return render_template('index.html', samples=samples, model_exists=model_exists)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    return redirect(url_for('index'))

@app.route('/label', methods=['POST'])
def label_sample():
    sample_id = request.form.get('sample_id')
    label = request.form.get('label')
    
    if sample_id and label:
        labels = load_labels()
        labels[sample_id] = int(label)
        save_labels(labels)
    
    return redirect(url_for('index'))

@app.route('/visualize/<sample_id>')
def visualize_sample(sample_id):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{sample_id}.csv")
    if not os.path.exists(filepath):
        return jsonify({'error': 'Sample not found'}), 404
    
    df = pd.read_csv(filepath)
    
    oscillogram = create_plot(df, 'oscillogram')
    fft_plot = create_plot(df, 'fft')
    wavelet_plot = create_plot(df, 'wavelet')
    
    return jsonify({
        'oscillogram': oscillogram,
        'fft_plot': fft_plot,
        'wavelet_plot': wavelet_plot
    })

@app.route('/predict', methods=['POST'])
def predict():
    sample_id = request.form.get('sample_id')
    if not sample_id:
        return jsonify({'error': 'Sample ID not provided'}), 400
    
    model = load_model()
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{sample_id}.csv")
    if not os.path.exists(filepath):
        return jsonify({'error': 'Sample file not found'}), 404
    
    try:
        input_data = prepare_sample_for_prediction(filepath)
        prediction = model.predict(input_data)
        predicted_class = int(prediction.predict[0])
        
        return jsonify({
            'sample_id': sample_id,
            'predicted_class': predicted_class
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('data/models', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)