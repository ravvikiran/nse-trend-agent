"""
Simplified integration test for Watchlist API.
Tests without requiring network calls or complex mocking.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from unittest.mock import MagicMock, patch
from api import app, init_api
import json

def test_watchlist_basic():
    """Test that watchlist API routes are registered and basic responses work."""
    print("Testing Watchlist API basic functionality...")

    # Create mocks
    mock_tj = MagicMock()
    mock_tj.get_open_trades.return_value = []
    mock_tj.get_all_trades.return_value = []

    mock_df = MagicMock()
    mock_ms = MagicMock()
    mock_ms.get_market_status.return_value = "OPEN"

    # Create a watchlist manager that doesn't actually fetch data
    wm = MagicMock()
    wm.get_watchlist_with_analysis.return_value = [
        {
            'id': '1',
            'symbol': 'TEST',
            'added_at': '2026-04-30T00:00:00',
            'notes': '',
            'analysis': {
                'symbol': 'TEST',
                'recommendation': 'BUY',
                'confidence': 7,
                'current_price': 100.0,
                'entry_zone': '₹98.00 - ₹102.00',
                'stop_loss': 95.0,
                'stop_loss_pct': 5.0,
                'target1': 110.0,
                'target1_pct': 10.0,
                'target2': 120.0,
                'target2_pct': 20.0,
                'reasoning': 'Test',
                'risk_assessment': 'LOW',
                'technical_signals': ['✅ Signal 1', '📈 Signal 2'],
                'timestamp': '2026-04-30T00:00:00'
            }
        }
    ]
    wm.add_multiple_stocks.return_value = {'RELIANCE': True, 'TCS': True}
    wm.remove_stock.return_value = True
    wm.analyze_stock.return_value = MagicMock(
        symbol='RELIANCE',
        recommendation='BUY',
        confidence=6,
        current_price=1430.80,
        entry_zone='₹1413.98 - ₹1447.62',
        stop_loss=1346.71,
        stop_loss_pct=5.9,
        target1=1565.34,
        target1_pct=9.4,
        target2=1632.60,
        target2_pct=14.1,
        reasoning='Bullish setup',
        risk_assessment='MEDIUM',
        technical_signals=['📈 Near 20-day high', '📊 Elevated volume'],
        timestamp='2026-04-30T00:00:00',
        to_dict=lambda: {
            'symbol': 'RELIANCE',
            'recommendation': 'BUY',
            'confidence': 6,
            'current_price': 1430.80,
            'entry_zone': '₹1413.98 - ₹1447.62',
            'stop_loss': 1346.71,
            'stop_loss_pct': 5.9,
            'target1': 1565.34,
            'target1_pct': 9.4,
            'target2': 1632.60,
            'target2_pct': 14.1,
            'reasoning': 'Bullish setup',
            'risk_assessment': 'MEDIUM',
            'technical_signals': ['📈 Near 20-day high', '📊 Elevated volume'],
            'timestamp': '2026-04-30T00:00:00'
        }
    )

    # Initialize API
    init_api(
        trade_journal_inst=mock_tj,
        data_fetcher_inst=mock_df,
        market_scheduler_inst=mock_ms,
        watchlist_manager_inst=wm
    )

    with app.test_client() as client:
        # Test 1: GET /api/watchlist
        print("\n1. GET /api/watchlist")
        resp = client.get('/api/watchlist')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'watchlist' in data
        assert len(data['watchlist']) >= 1
        print(f"   ✓ Returns {len(data['watchlist'])} items")

        # Test 2: POST /api/watchlist - single symbol string
        print("\n2. POST /api/watchlist (single string)")
        resp = client.post('/api/watchlist',
            data=json.dumps({'symbols': 'RELIANCE'}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] == True
        print(f"   ✓ Added: {data['added']}")

        # Test 3: POST /api/watchlist - multiple symbols
        print("\n3. POST /api/watchlist (list)")
        resp = client.post('/api/watchlist',
            data=json.dumps({'symbols': ['TCS', 'INFY']}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['added']) == 2
        print(f"   ✓ Added {len(data['added'])} symbols")

        # Test 4: DELETE /api/watchlist/<symbol>
        print("\n4. DELETE /api/watchlist/<symbol>")
        resp = client.delete('/api/watchlist/TCS')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['success'] == True
        print("   ✓ Delete successful")

        # Test 5: DELETE non-existent
        print("\n5. DELETE non-existent symbol")
        wm.remove_stock.return_value = False
        resp = client.delete('/api/watchlist/UNKNOWN')
        assert resp.status_code == 404  # Not found
        data = json.loads(resp.data)
        assert data['success'] == False
        print("   ✓ Returns 404 for non-existent")
        wm.remove_stock.return_value = True

        # Test 6: GET /api/watchlist/analyze/<symbol>
        print("\n6. GET /api/watchlist/analyze/<symbol>")
        resp = client.get('/api/watchlist/analyze/RELIANCE')
        assert resp.status_code == 200
        analysis = json.loads(resp.data)
        assert 'recommendation' in analysis
        assert 'confidence' in analysis
        print(f"   ✓ Analysis: {analysis['recommendation']} (conf: {analysis['confidence']}/10)")

        # Test 7: POST without symbols
        print("\n7. POST /api/watchlist (invalid - no symbols)")
        resp = client.post('/api/watchlist',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        print("   ✓ Properly rejects invalid request")

        # Test 8: Page route
        print("\n8. GET /watchlist (page)")
        resp = client.get('/watchlist')
        assert resp.status_code == 200
        assert b'Watchlist' in resp.data
        print("   ✓ Page renders")

    print("\n✅ All Watchlist API tests passed!")
    return True

if __name__ == '__main__':
    try:
        test_watchlist_basic()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
