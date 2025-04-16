import json
import requests
from collections import deque
from fastapi import FastAPI
from paho.mqtt import client as mqtt_client
import uvicorn
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime

app = FastAPI()

# Конфигурация MQTT
MQTT_BROKER = "192.168.0.67"
MQTT_PORT = 1883
MQTT_TOPIC_DATA_READY = "Data"
MQTT_TOPIC_URL = "URL"
DEVICE_API_URL = None

class DataSample:
    def __init__(self):
        self.values = []
        self.timestamp = None
        self.sample_rate = None
        self.resolution = None
        self.device_id = None

    def update(self, data):
        self.values = data.get('current', []) + data.get('mic', []) + data.get('vibro', [])
        metadata = data.get('metadata', {})
        self.timestamp = metadata.get('timestamp')
        self.sample_rate = metadata.get('sample_rate')
        self.resolution = metadata.get('resolution')
        self.device_id = metadata.get('device_id')

# Буферы для хранения данных
BUFFER_SIZE = 10
data_buffer = deque(maxlen=BUFFER_SIZE)

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            client.subscribe(MQTT_TOPIC_DATA_READY)
            client.subscribe(MQTT_TOPIC_URL)
        else:
            print(f"Failed to connect, return code {rc}")

    client = mqtt_client.Client()
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client

def on_message(client, userdata, msg):
    global DEVICE_API_URL
    
    if msg.topic == MQTT_TOPIC_URL:
        DEVICE_API_URL = f"http://{msg.payload.decode()}/get_data"
        print(f"Device URL updated: {DEVICE_API_URL}")
    
    elif msg.topic == MQTT_TOPIC_DATA_READY and msg.payload.decode() == "1":
        print("Data ready flag received")
        if DEVICE_API_URL:
            fetch_sensor_data()

def fetch_sensor_data():
    try:
        response = requests.get(DEVICE_API_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            sample = DataSample()
            sample.update(data)
            data_buffer.append(sample)
            
            print(f"New data received from {sample.device_id} at {sample.timestamp}")
            print(f"Sample rate: {sample.sample_rate}, Resolution: {sample.resolution} bits")
            
    except Exception as e:
        print(f"Error fetching data: {e}")

# API Endpoints
@app.get("/averages")
async def get_averages():
    """Возвращает средние значения последней выборки"""
    if not data_buffer:
        return {"message": "No data available"}
    
    last_sample = data_buffer[-1]
    return {
        "current_avg": sum(last_sample.values[:len(last_sample.values)//3]) / (len(last_sample.values)//3),
        "mic_avg": sum(last_sample.values[len(last_sample.values)//3:2*len(last_sample.values)//3]) / (len(last_sample.values)//3),
        "vibro_avg": sum(last_sample.values[2*len(last_sample.values)//3:]) / (len(last_sample.values)//3),
        "timestamp": last_sample.timestamp
    }

@app.get("/samples")
async def get_samples():
    """Возвращает все сохраненные семплы с метаданными"""
    return JSONResponse(content=jsonable_encoder({
        "samples": [{
            "values": sample.values,
            "timestamp": sample.timestamp,
            "sample_rate": sample.sample_rate,
            "resolution": sample.resolution,
            "device_id": sample.device_id
        } for sample in data_buffer]
    }))

@app.get("/metadata")
async def get_metadata():
    """Возвращает метаданные последней выборки"""
    if not data_buffer:
        return {"message": "No data available"}
    
    last_sample = data_buffer[-1]
    return {
        "timestamp": last_sample.timestamp,
        "sample_rate": last_sample.sample_rate,
        "resolution": last_sample.resolution,
        "device_id": last_sample.device_id
    }

def run():
    client = connect_mqtt()
    client.on_message = on_message
    client.loop_start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    run()