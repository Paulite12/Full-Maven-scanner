import unittest
from app import analyze_market

class AnalysisTests(unittest.TestCase):
    def test_relative_volume_and_move_score(self):
        candles=[]
        for i in range(12):
            candles.append({'ts':i,'open':1,'high':1.1,'low':.9,'close':1 if i<11 else 1.03,'volume':10,'turnover':100 if i<11 else 500})
        ticker={'symbol':'TESTUSDT','lastPrice':'1.03','price24hPcnt':'0.02','turnover24h':'1000000'}
        row=analyze_market(ticker,candles,'Bybit Spot')
        self.assertEqual(row['symbol'],'TESTUSDT')
        self.assertGreater(row['relative_volume'],1)
        self.assertGreaterEqual(row['score'],0)
        self.assertIn(row['assessment'],{'Monitoring','Watch','Early activity','Risk'})
    def test_empty_candles_are_safe(self):
        row=analyze_market({'symbol':'ABCUSDT','lastPrice':'0.5','price24hPcnt':'-0.12','turnover24h':'50000'},[],'Bybit Spot')
        self.assertEqual(row['symbol'],'ABCUSDT')
        self.assertEqual(row['change_24h'],-12)
        self.assertTrue(row['risk_flags'])
if __name__=='__main__':unittest.main()
