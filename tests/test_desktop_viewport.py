import unittest
from module.device.method.desktop_impl import desktop_fit_client_size

class ViewportTests(unittest.TestCase):
    def test_oversized_cross_over_client_fits_verified_mouse_extent(self):
        self.assertEqual(desktop_fit_client_size((1136,640),(1024,768)),(1022,576))

    def test_valid_native_size_is_preserved(self):
        self.assertIsNone(desktop_fit_client_size((1022,576),(1024,768)))
        self.assertIsNone(desktop_fit_client_size((1280,720),(1920,1080)))

    def test_invalid_metrics_do_not_resize(self):
        self.assertIsNone(desktop_fit_client_size((1136,640),(0,0)))
