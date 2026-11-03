import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch,Mock
import numpy as np
from module.device.method.macos_capture import crop_client, capture_window, launch_window

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).parents[1] / 'deploy/macos/capture_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class MacOSCaptureTests(unittest.TestCase):
    def test_title_must_be_unique(self):
        self.assertEqual(bridge.find_window([{'title': 'one', 'id': 1}, {'title': 'two', 'id': 2}], 'two'), 2)
        for windows in ([], [{'title': 'one', 'id': 1}, {'title': 'one', 'id': 2}]):
            with self.assertRaises(ValueError):
                bridge.find_window(windows, 'one')

    def test_titlebar_retina_and_rgb(self):
        frame = np.zeros((148, 200, 3), dtype=np.uint8)
        frame[:48] = 255
        frame[48:] = (1, 2, 3)
        result = crop_client(frame, (100, 50), (100, 50))
        self.assertEqual(result.shape, (50, 100, 3))
        np.testing.assert_array_equal(result[0, 0], [3, 2, 1])

    def test_invalid_frame(self):
        for frame, size in ((None, (100, 50)), (np.zeros((10, 100, 3), np.uint8), (100, 50))):
            with self.assertRaises(ValueError):
                crop_client(frame, size, (100, 50))

    @patch('module.device.method.macos_capture.requests.get')
    def test_remote_endpoint_rejected_before_token_transmission(self, get):
        with self.assertRaises(ValueError):
            capture_window('http://example.com', 'secret', 'one', (100, 50), (100, 50))
        get.assert_not_called()

    @patch('module.device.method.macos_capture.requests.get')
    def test_http_error_not_returned_as_frame(self, get):
        get.return_value.raise_for_status.side_effect = RuntimeError('403')
        with self.assertRaises(RuntimeError):
            capture_window('http://127.0.0.1:22271', 'secret', 'one', (100, 50), (100, 50))

    @patch('module.device.method.macos_capture.time.sleep')
    @patch('module.device.method.macos_capture.requests.get')
    def test_temporary_capture_failure_retries_read_only(self,get,sleep):
        import cv2
        bad=Mock(status_code=503)
        ok=Mock(status_code=200,content=cv2.imencode('.png',np.zeros((50,100,3),np.uint8))[1].tobytes())
        get.side_effect=[bad,ok]
        self.assertEqual(capture_window('http://127.0.0.1:22272','secret','one',(100,50),(100,50)).shape,(50,100,3))
        self.assertEqual(get.call_count,2)
        bad.raise_for_status.assert_not_called()

    @patch('module.device.method.macos_capture.time.sleep')
    @patch('module.device.method.macos_capture.requests.get')
    def test_persistent_capture_failure_stops_after_three(self,get,sleep):
        bad=Mock(status_code=503)
        bad.raise_for_status.side_effect=RuntimeError('503')
        get.return_value=bad
        with self.assertRaises(RuntimeError):capture_window('http://127.0.0.1:22272','secret','one',(100,50),(100,50))
        self.assertEqual(get.call_count,3)

    @patch('module.device.method.macos_capture.requests.post')
    def test_launch_sends_only_configured_title(self, post):
        post.return_value.json.return_value = {'started': True}
        launch_window('http://127.0.0.1:22272', 'secret', 'account-1')
        self.assertEqual(post.call_args.kwargs['json'], {'title': 'account-1'})
        self.assertEqual(post.call_args.args[0], 'http://127.0.0.1:22272/launch')

    @patch('module.device.method.macos_capture.requests.post')
    def test_remote_launch_rejected(self, post):
        with self.assertRaises(ValueError):
            launch_window('http://example.com', 'secret', 'account-1')
        post.assert_not_called()

    @patch('module.device.method.macos_capture.requests.post')
    def test_launch_requires_positive_confirmation(self, post):
        post.return_value.json.return_value = {'started': False}
        with self.assertRaises(RuntimeError):
            launch_window('http://127.0.0.1:22272', 'secret', 'account-1')


if __name__ == '__main__':
    unittest.main()
