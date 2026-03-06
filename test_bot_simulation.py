import time
import logging
import torch
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5
from live_bot import LiveTradingBot
import config

# Setup logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_bot")

def test_simulation():
    print("\n" + "="*50)
    print("🚀 STARTING BOT SIMULATION TEST")
    print("="*50 + "\n")

    # 1. Initialize Bot
    print("Step 1: Initializing Bot...")
    bot = LiveTradingBot()
    
    # SAFETY: Explicitly mark as simulation
    print("Step 1b: Verifying Safe Mode...")
    if not bot.initialize_mt5():
        print("❌ Failed to connect to MT5 for safety check")
        return
        
    account = mt5.account_info()
    if account and account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        print("\n" + "!"*60)
        print("⛔ CRITICAL SAFETY ERROR: CANNOT RUN SIMULATION ON REAL ACCOUNT")
        print("!"*60 + "\n")
        return

    # Force load model (usually background, but we need it now)
    print("Step 2: Loading AI Model (FinBERT)...")
    bot.initialize_finbert()  # Corrected method name
    
    if bot.model and bot.tokenizer:
        print(f"Model ID2Label: {bot.model.config.id2label}")
        
    # 2. Connect to MT5
    print("\nStep 3: Connecting to MT5...")
    if not bot.initialize_mt5():
        print("❌ Failed to connect to MT5")
        return

    # 3. Create Mock Events
    print("\nStep 4: Creating Simulation Events...")
    now = datetime.now(timezone.utc)
    
    # Pre-News Event (Weak/Ambiguous Headline)
    pre_news_event_weak = {
        'id': 'sim_weak',
        'name': 'SIMULATION: Pre-News Weak',
        'time': now + timedelta(minutes=3),
        'currency': 'USD',
        'impact': 'Medium',
        'headline': 'Market waits for upcoming data release',
        'source': 'Simulation'
    }

    # Pre-News Event (Strong Positive)
    pre_news_event = {
        'id': 'sim_1',
        'name': 'SIMULATION: Pre-News Positive',
        'time': now + timedelta(minutes=2),
        'currency': 'USD',
        'impact': 'High',
        'headline': 'USD Skyrockets as Inflation Hits Record High',
        'source': 'Simulation'
    }
    
    # Post-News Event (Actual > Forecast -> Positive)
    post_news_event = {
        'id': 'sim_2',
        'name': 'SIMULATION: Post-News Beat',
        'time': now - timedelta(minutes=1),
        'currency': 'USD',
        'impact': 'High',
        'forecast': '2.0%',
        'actual': '3.5%',
        'source': 'Simulation'
    }
    
    bot.events = [pre_news_event_weak, pre_news_event, post_news_event]
    print(f"✅ Injected 3 events: 2 Future (1 Weak, 1 Strong), 1 Past (Post-News)")
    
    # 4. Run Logic
    print("\nStep 5: Executing Trade Logic...")
    
    # Debug Sentiment for Pre-News
    if bot.model:
        for ev in [pre_news_event_weak, pre_news_event]:
            inputs = bot.tokenizer(ev['headline'], return_tensors="pt", truncation=True, max_length=128, padding=True)
            outputs = bot.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1)
            print(f"DEBUG: Raw Probabilities for '{ev['headline']}': {probs}")
        
    bot.execute_trade_logic()
    
    # 5. Report Results
    print("\n" + "="*50)
    print("📊 SIMULATION RESULTS")
    print("="*50)
    
    if len(bot.trade_history) > 0:
        for i, trade in enumerate(bot.trade_history):
            print(f"\n[Trade #{i+1}]")
            print(f"  Event:    {trade['event']}")
            print(f"  Strategy: {trade['strategy']}")
            print(f"  Signal:   {trade['signal']}")
            print(f"  Status:   {trade['status']}")
            if 'reason' in trade:
                print(f"  Reason:   {trade['reason']}")
        print(f"\n✅ SUCCESS: Generated {len(bot.trade_history)} trades.")
    else:
        print("\n❌ FAILURE: No trades were generated.")
        print("Possible reasons:")
        print("  - Algo Trading is disabled in MT5")
        print("  - Config thresholds are too high")
        print("  - MT5 connection issues")

if __name__ == "__main__":
    test_simulation()
