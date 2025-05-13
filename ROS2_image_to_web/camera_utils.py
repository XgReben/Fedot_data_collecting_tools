import cv2
import numpy as np
import json
from pathlib import Path

def load_calibration():
    calibration_file = Path("calibration.json")
    if calibration_file.exists():
        with open(calibration_file) as f:
            return json.load(f)
    return {
        "camera_matrix": [[800,0,320],[0,800,240],[0,0,1]],
        "dist_coeffs": [-0.1,0.05,0.001,0.002,0.0]
    }

def save_calibration(data):
    with open("calibration.json", "w") as f:
        json.dump(data, f)

def load_config():
    config_file = Path("config.json")
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {
        "use_correction": True,
        "enable_processing": True,
        "gamma": 1.2,
        "blur_kernel": 7
    }

def save_config(config):
    with open("config.json", "w") as f:
        json.dump(config, f)

def correct_lens_distortion(image, camera_matrix, dist_coeffs):
    h, w = image.shape[:2]
    new_cam_matrix, roi = cv2.getOptimalNewCameraMatrix(
        np.array(camera_matrix),
        np.array(dist_coeffs),
        (w, h),
        1,
        (w, h)
    )
    undistorted = cv2.undistort(
        image,
        np.array(camera_matrix),
        np.array(dist_coeffs),
        None,
        new_cam_matrix
    )
    #x, y, w, h = roi
    return undistorted

def apply_gamma_correction(image, gamma=1.0):
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255
        for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def find_contours(image, threshold=100):
    img_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, thresh_img = cv2.threshold(img_grey, threshold, 255, cv2.THRESH_BINARY)
    contours, hierarchy = cv2.findContours(thresh_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image, contours, -1, (255,255,255), 1)
    return contours, hierarchy

def detect_chessboard(image, pattern_size):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(
        gray, pattern_size,
        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
    )
    if ret:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
    return ret, corners

def draw_chessboard_corners(image, corners, pattern_size):
    cv2.drawChessboardCorners(image, pattern_size, corners, True)
    return image
