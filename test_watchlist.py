"""
Quick test for WatchlistManager analysis functionality.
Run: python test_watchlist.py
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.data_fetcher import DataFetcher
from core.indicator_engine import IndicatorEngine
from watchlist.watchlist_manager import WatchlistManager

def test_watchlist_analysis():
    """Test watchlist analysis for a sample stock."""
    print("Initializing components...")
    data_fetcher = DataFetcher(period=200, interval='1D')
    indicator_engine = IndicatorEngine()

    wm = WatchlistManager(
        data_dir='data',
        data_fetcher=data_fetcher,
        indicator_engine=indicator_engine
    )

    print("\nTesting analysis for RELIANCE...")
    analysis = wm.analyze_stock('RELIANCE')

    if analysis:
        print(f"\n✓ Analysis successful for {analysis.symbol}")
        print(f"  Recommendation: {analysis.recommendation}")
        print(f"  Confidence: {analysis.confidence}/10")
        print(f"  Current Price: ₹{analysis.current_price:.2f}")
        print(f"  Entry Zone: {analysis.entry_zone}")
        print(f"  Stop Loss: ₹{analysis.stop_loss:.2f} ({analysis.stop_loss_pct:.1f}%)")
        print(f"  Target 1: ₹{analysis.target1:.2f} (+{analysis.target1_pct:.1f}%)")
        print(f"  Target 2: ₹{analysis.target2:.2f} (+{analysis.target2_pct:.1f}%)")
        print(f"  Reasoning: {analysis.reasoning}")
        print(f"  Risk: {analysis.risk_assessment}")
        print(f"\n  Technical Signals:")
        for signal in analysis.technical_signals:
            print(f"    • {signal}")
    else:
        print("✗ Analysis failed")
        return False

    print("\n\nTesting add/remove functionality...")
    # Test adding
    result = wm.add_stock('TCS')
    print(f"Add TCS: {'Success' if result else 'Already exists'}")

    result = wm.add_stock('INFY')
    print(f"Add INFY: {'Success' if result else 'Already exists'}")

    # List watchlist
    items = wm.get_watchlist()
    print(f"\nWatchlist now has {len(items)} items: {[i['symbol'] for i in items]}")

    # Test remove
    wm.remove_stock('TCS')
    items = wm.get_watchlist()
    print(f"After removing TCS: {[i['symbol'] for i in items]}")

    print("\n✓ All tests passed!")
    return True

if __name__ == '__main__':
    try:
        success = test_watchlist_analysis()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
