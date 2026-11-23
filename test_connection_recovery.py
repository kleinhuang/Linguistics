"""Offline regression tests; no requests to Arctic Shift."""
import http.client
import unittest
from unittest.mock import patch
import shift_corpus_engine as engine

class Response:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def read(self):
        return self.data

class RecoveryTests(unittest.TestCase):
    def test_reset_during_response_read_retries(self):
        class ResetResponse(Response):
            def read(self):
                raise ConnectionResetError(54, 'Connection reset by peer')
        with patch.object(engine.urllib.request, 'urlopen', side_effect=[ResetResponse(b''), Response(b'{"data":[]}')]) as api, patch.object(engine.time,'sleep'):
            self.assertEqual(engine.fetch_page([('limit','1')], 1), [])
            self.assertEqual(api.call_count,2)

    def test_truncated_chunk_retries(self):
        class BrokenResponse(Response):
            def read(self):
                raise http.client.IncompleteRead(b'{', 10)
        with patch.object(engine.urllib.request, 'urlopen', side_effect=[BrokenResponse(b''), Response(b'{"data":[]}')]) as api, patch.object(engine.time,'sleep'):
            self.assertEqual(engine.fetch_page([('limit','1')],1), [])
            self.assertEqual(api.call_count,2)

    def test_reset_exhaustion_becomes_api_error(self):
        with patch.object(engine.urllib.request,'urlopen',side_effect=ConnectionResetError(54,'reset')) as api, patch.object(engine.time,'sleep'):
            with self.assertRaises(engine.ApiError):
                engine.fetch_page([('limit','1')],1)
            self.assertEqual(api.call_count,5)

if __name__ == '__main__':
    unittest.main()
