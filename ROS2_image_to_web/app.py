import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from flask import Flask, render_template, Response, jsonify, request
import cv2
import numpy as np
from camera_utils import * 
import threading
import os
import shutil
from flask import send_from_directory, send_file
from werkzeug.utils import secure_filename
import zipfile
from pathlib import Path
import datetime
from collections import deque

Path("dataset/images").mkdir(parents=True, exist_ok=True)
Path("dataset/labels").mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

class CameraSubscriber(Node):
    def __init__(self):
        super().__init__('camera_subscriber')
        self.subscription = self.create_subscription(
            Image,
            '/image_raw',
            self.listener_callback,
            10
        )
        self.bridge = CvBridge()
        self.frame = np.zeros((480,640,3))
        self.calibration = load_calibration()
        self.config = load_config()
        self.calibration_frames = []
        self.chessboard_lock = threading.Lock()

    def listener_callback(self, msg):
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        
        if self.config.get('blur_kernel', 7) > 0:
            self.frame = cv2.medianBlur(self.frame, self.config['blur_kernel'])
        
        if self.config.get('use_correction', True):
            self.frame = correct_lens_distortion(
                self.frame,
                self.calibration['camera_matrix'],
                self.calibration['dist_coeffs']
            )
        
        if self.config.get('enable_processing', True):
            self.frame = apply_gamma_correction(self.frame, self.config.get('gamma', 1.2))
            find_contours(self.frame)

def gen_frame():
    while True:
        rclpy.spin_once(camera_subscriber)
        frame = camera_subscriber.frame
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  # concat frame one by one and show result

@app.route('/video_feed')
def video_feed():
    #Video streaming route. Put this in the src attribute of an img tag
    return Response(gen_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')


@app.route('/calibrate', methods=['POST'])
def calibrate():
    data = request.get_json()
    camera_subscriber.calibration.update(data)
    save_calibration(camera_subscriber.calibration)
    return jsonify(status="success")

@app.route('/config', methods=['POST'])
def update_config():
    camera_subscriber.config.update(request.get_json())
    save_config(camera_subscriber.config)
    return jsonify(status="success")

@app.route('/calibrations')
def calibrations_page():
    return render_template('calibrations.html')


@app.route('/calibration_feed')
def calibration_feed():
    def gen():
        while True:
            frame = correct_lens_distortion(
                camera_subscriber.frame.copy(),
                camera_subscriber.calibration['camera_matrix'],
                camera_subscriber.calibration['dist_coeffs']
            )
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture_frame', methods=['POST'])
def capture_frame():
    try:
        with camera_subscriber.chessboard_lock:
            gray = cv2.cvtColor(camera_subscriber.frame, cv2.COLOR_BGR2GRAY)
            ret, corners = cv2.findChessboardCorners(
                gray, 
                (int(request.json['width']), int(request.json['height'])),
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK
            )
            
            if not ret:
                return jsonify(
                    status="error", 
                    message="Не удалось найти шахматную доску. Проверьте освещение и настройки"
                ), 400
            
            camera_subscriber.calibration_frames.append({
                'corners': corners.tolist(),
                'image_size': gray.shape[::-1]
            })
            return jsonify(status="success", corners_found=True)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

@app.route('/calibrate/chessboard', methods=['POST'])
def calibrate_chessboard():
    data = request.get_json()
    objp = np.zeros((data['width']*data['height'],3), np.float32)
    objp[:,:2] = np.mgrid[0:data['width'],0:data['height']].T.reshape(-1,2)
    objp *= data['square_size']
    
    objpoints = [objp for _ in range(len(camera_subscriber.calibration_frames))]
    imgpoints = [np.array(f['corners']) for f in camera_subscriber.calibration_frames]
    
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints,
        imgpoints,
        tuple(camera_subscriber.calibration_frames[0]['image_size']),
        None, None
    )
    if ret:
        camera_subscriber.calibration.update({
            'camera_matrix': mtx.tolist(),
            'dist_coeffs': dist.tolist()
        })
        save_calibration(camera_subscriber.calibration)
        return jsonify(
            camera_matrix=mtx.tolist(),
            dist_coeffs=dist.tolist()[0],
            reprojection_error=ret
        )
    return jsonify(status="error"), 500

@app.route('/current_calibration')
def get_current_calibration():
    return jsonify({
        'camera_matrix': camera_subscriber.calibration['camera_matrix'],
        'dist_coeffs': camera_subscriber.calibration['dist_coeffs']
    })

@app.route('/chessboard_feed')
def chessboard_feed():
    def gen():
        while True:
            frame = camera_subscriber.frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ret, corners = cv2.findChessboardCorners(
                gray, 
                (9,6),  # Default pattern size
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK
            )
            if ret:
                cv2.drawChessboardCorners(frame, (9,6), corners, ret)
            ret, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/capture_image', methods=['POST'])
def capture_image():
    try:
        os.makedirs('dataset/images', exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dataset/images/{timestamp}.jpg"
        cv2.imwrite(filename, camera_subscriber.frame)
        return jsonify(status="success", filename=filename)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500



@app.route('/download_dataset')
def download_dataset():
    if not os.path.exists('dataset/images'):
        return jsonify(status="error", message="Dataset is empty"), 404
    
    try:
        shutil.make_archive('dataset', 'zip', 'dataset')
        return send_file('dataset.zip', as_attachment=True, mimetype='application/zip')
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500
    finally:
        if os.path.exists('dataset.zip'):
            os.remove('dataset.zip') 

@app.route('/clear_dataset', methods=['POST'])
def clear_dataset():
    if os.path.exists('dataset'):
        shutil.rmtree('dataset')
    os.makedirs('dataset/images', exist_ok=True)
    os.makedirs('dataset/labels', exist_ok=True)
    return jsonify(status="success")

@app.route('/reset_calibration_frames', methods=['POST'])
def reset_calibration_frames():
    camera_subscriber.calibration_frames = []
    return jsonify(status="success", count=0)

@app.route('/calibration_frames_count')
def calibration_frames_count():
    return jsonify(count=len(camera_subscriber.calibration_frames))

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response

if __name__ == '__main__':
    rclpy.init(args=None)
    camera_subscriber = CameraSubscriber()

    app.run(host='192.168.1.28', port=8080, debug=True)
    # camera_subscriber.destroy_node()
    # rclpy.shutdown()


