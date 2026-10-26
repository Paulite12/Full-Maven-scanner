import os, tempfile, unittest
from fastapi.testclient import TestClient
import app as scanner

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.NamedTemporaryFile(delete=False);self.tmp.close()
        self.old_path=scanner.DB_PATH;self.old_url=scanner.DATABASE_URL
        scanner.DB_PATH=self.tmp.name;scanner.DATABASE_URL='';scanner.init_db()
        self.client=TestClient(scanner.app)
    def tearDown(self):
        self.client.close();scanner.DB_PATH=self.old_path;scanner.DATABASE_URL=self.old_url
        try:os.unlink(self.tmp.name)
        except OSError:pass
    def test_health(self):
        r=self.client.get('/health');self.assertEqual(r.status_code,200);self.assertTrue(r.json()['ok'])
    def test_dashboard(self):
        r=self.client.get('/');self.assertEqual(r.status_code,200);self.assertIn('Full Maven Scanner',r.text)
    def test_market_empty(self):
        r=self.client.get('/api/market');self.assertEqual(r.status_code,200);self.assertIn('rows',r.json())
    def test_config_does_not_trade(self):
        r=self.client.get('/api/config');self.assertEqual(r.status_code,200);self.assertFalse(r.json()['trading_enabled'])
if __name__=='__main__':unittest.main()
