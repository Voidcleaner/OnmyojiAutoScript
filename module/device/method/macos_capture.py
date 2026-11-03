"""CrossOver capture using an authenticated macOS host bridge (RGB output)."""
from urllib.parse import urlsplit
import cv2
import numpy as np
import requests
import time


def crop_client(image, client_size, target_size):
    width, height = client_size
    if width <= 0 or height <= 0 or image is None:
        raise ValueError('Invalid client size or screenshot')
    # screencapture -o excludes the shadow. CrossOver's macOS window adds its
    # title bar above the client. Capture pixels may be Retina scaled.
    scale = image.shape[1] / width
    client_height = round(height * scale)
    if client_height > image.shape[0]:
        raise ValueError('Screenshot is smaller than the client area')
    client = image[-client_height:, :]
    return cv2.cvtColor(cv2.resize(client, target_size), cv2.COLOR_BGR2RGB)


def capture_window(url, token, title, client_size, target_size):
    endpoint = urlsplit(url)
    if (endpoint.scheme != 'http' or endpoint.hostname != '127.0.0.1'
            or endpoint.username or endpoint.password or not token or not title):
        raise ValueError('macOS capture requires a loopback URL, token and unique window title')
    for attempt in range(3):
        response = requests.get(url.rstrip('/') + '/capture', params={'title': title},
                                headers={'Authorization': 'Bearer ' + token}, timeout=12)
        if response.status_code==503 and attempt<2:
            time.sleep(.5)
            continue
        response.raise_for_status()
        break
    image = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    return crop_client(image, client_size, target_size)


def launch_window(url, token, title):
    endpoint = urlsplit(url)
    if (endpoint.scheme != 'http' or endpoint.hostname != '127.0.0.1'
            or endpoint.username or endpoint.password or not token or not title):
        raise ValueError('macOS launch requires a loopback URL, token and unique title')
    response = requests.post(url.rstrip('/') + '/launch', json={'title': title},
                             headers={'Authorization': 'Bearer ' + token}, timeout=15)
    response.raise_for_status()
    if response.json().get('started') is not True:
        raise RuntimeError('macOS host did not confirm launch')
