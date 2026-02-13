#!/usr/bin/env python3
"""
Trading Bot - Paper trading with strategy tracking
Usage:
    python bot.py status              # Account status
    python bot.py buy VCP AAPL 10     # Buy 10 AAPL using VCP strategy
    python bot.py sell VCP AAPL       # Sell AAPL position (VCP strategy)
    python bot.py positions           # Show all positions
    python bot.py stats               # Show trading stats by strategy
    python bot.py stats VCP           # Show VCP strategy stats only
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from config import STRATEGIES, DEFAULT_STOP_LOSS_PCT, DEFAULT_TARGET_PCT
from alpaca_client import client
from tracker import tracker, Trade


def cmd_status():
    """Show account status"""
    acct = client.get_account()
    print(f"""
📈 ALPACA PAPER ACCOUNT
━━━━━━━━━━━━━━━━━━━━━━
Equity:       ${float(acct['equity']):>12,.2f}
Cash:         ${float(acct['cash']):>12,.2f}
Buying Power: ${float(acct['buying_power']):>12,.2f}
Day P&L:      ${float(acct.get('equity', 0)) - float(acct.get('last_equity', acct.get('equity', 0))):>12,.2f}
""")


def cmd_buy(strategy: str, symbol: str, qty: int = None, dollars: float = None):
    """Buy stock with strategy tag"""
    strategy = strategy.upper()
    symbol = symbol.upper()
    
    if strategy not in STRATEGIES:
        print(f"❌ Unknown strategy: {strategy}")
        print(f"   Valid: {', '.join(STRATEGIES.keys())}")
        return
    
    # Get current price
    try:
        quote = client.get_quote(symbol)
        price = float(quote.get('ap', 0)) or float(quote.get('bp', 0))  # ask or bid
        if not price:
            bars = client.get_bars(symbol, limit=1)
            if bars:
                price = bars[-1]['c']
    except Exception as e:
        print(f"❌ Could not get price for {symbol}: {e}")
        return
    
    # Calculate quantity if dollars specified
    if dollars and not qty:
        qty = int(dollars / price)
    elif not qty:
        qty = 1
    
    # Generate client order ID
    client_order_id = f"{strategy}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Place order
    try:
        order = client.place_order(
            symbol=symbol,
            qty=qty,
            side="buy",
            order_type="market",
            client_order_id=client_order_id
        )
        
        # Calculate stops
        stop_loss = price * (1 - DEFAULT_STOP_LOSS_PCT)
        target = price * (1 + DEFAULT_TARGET_PCT)
        
        # Track trade
        trade = Trade(
            symbol=symbol,
            strategy=strategy,
            side="buy",
            qty=qty,
            entry_price=price,
            stop_loss=stop_loss,
            target=target,
            order_id=order['id'],
            client_order_id=client_order_id
        )
        tracker.add_trade(trade)
        
        print(f"""
✅ ORDER PLACED
━━━━━━━━━━━━━━━━━━━━━━
Strategy:   {strategy} ({STRATEGIES[strategy]})
Symbol:     {symbol}
Quantity:   {qty}
Price:      ~${price:,.2f}
Total:      ~${price * qty:,.2f}
Stop Loss:  ${stop_loss:,.2f} (-{DEFAULT_STOP_LOSS_PCT*100:.0f}%)
Target:     ${target:,.2f} (+{DEFAULT_TARGET_PCT*100:.0f}%)
Order ID:   {order['id'][:8]}...
""")
    except Exception as e:
        print(f"❌ Order failed: {e}")


def cmd_sell(strategy: str, symbol: str, qty: int = None):
    """Sell position"""
    strategy = strategy.upper()
    symbol = symbol.upper()
    
    # Get current position
    pos = client.get_position(symbol)
    if not pos:
        print(f"❌ No position in {symbol}")
        return
    
    qty = qty or int(float(pos['qty']))
    current_price = float(pos['current_price'])
    
    # Generate client order ID
    client_order_id = f"{strategy}_{symbol}_SELL_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        order = client.place_order(
            symbol=symbol,
            qty=qty,
            side="sell",
            order_type="market",
            client_order_id=client_order_id
        )
        
        # Close trade in tracker
        trade = tracker.close_trade(symbol, current_price, strategy)
        
        pnl = float(pos['unrealized_pl'])
        pnl_pct = float(pos['unrealized_plpc']) * 100
        
        emoji = "🟢" if pnl >= 0 else "🔴"
        print(f"""
{emoji} SOLD {symbol}
━━━━━━━━━━━━━━━━━━━━━━
Strategy:   {strategy}
Quantity:   {qty}
Price:      ${current_price:,.2f}
P&L:        ${pnl:,.2f} ({pnl_pct:+.2f}%)
""")
    except Exception as e:
        print(f"❌ Sell failed: {e}")


def cmd_positions():
    """Show all positions"""
    positions = client.get_positions()
    
    if not positions:
        print("📭 No open positions")
        return
    
    print("\n📊 OPEN POSITIONS")
    print("━" * 60)
    
    total_value = 0
    total_pnl = 0
    
    for pos in positions:
        symbol = pos['symbol']
        qty = float(pos['qty'])
        entry = float(pos['avg_entry_price'])
        current = float(pos['current_price'])
        value = float(pos['market_value'])
        pnl = float(pos['unrealized_pl'])
        pnl_pct = float(pos['unrealized_plpc']) * 100
        
        # Find strategy from tracker
        open_trades = tracker.get_open_trades()
        strat = "???"
        for t in open_trades:
            if t.symbol == symbol:
                strat = t.strategy
                break
        
        emoji = "🟢" if pnl >= 0 else "🔴"
        print(f"{emoji} {symbol:6} [{strat:4}] {qty:>6.0f} @ ${entry:>8.2f} → ${current:>8.2f}  {pnl_pct:>+6.1f}%  ${pnl:>+10.2f}")
        
        total_value += value
        total_pnl += pnl
    
    print("━" * 60)
    emoji = "🟢" if total_pnl >= 0 else "🔴"
    print(f"{emoji} TOTAL: ${total_value:,.2f}  P&L: ${total_pnl:+,.2f}")


def cmd_stats(strategy: str = None):
    """Show trading stats"""
    print(tracker.summary())
    
    if strategy:
        strategy = strategy.upper()
        stats = tracker.get_stats(strategy)
        print(f"\n📈 {strategy} Details:")
        print(f"   Trades: {stats['trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Avg Win: ${stats['avg_win']:,.2f}")
        print(f"   Avg Loss: ${stats['avg_loss']:,.2f}")
        print(f"   Total P&L: ${stats['total_pnl']:,.2f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1].lower()
    args = sys.argv[2:]
    
    if cmd == "status":
        cmd_status()
    elif cmd == "buy":
        if len(args) < 2:
            print("Usage: bot.py buy STRATEGY SYMBOL [QTY]")
            return
        strategy, symbol = args[0], args[1]
        qty = int(args[2]) if len(args) > 2 else None
        cmd_buy(strategy, symbol, qty)
    elif cmd == "sell":
        if len(args) < 2:
            print("Usage: bot.py sell STRATEGY SYMBOL [QTY]")
            return
        strategy, symbol = args[0], args[1]
        qty = int(args[2]) if len(args) > 2 else None
        cmd_sell(strategy, symbol, qty)
    elif cmd == "positions" or cmd == "pos":
        cmd_positions()
    elif cmd == "stats":
        strategy = args[0] if args else None
        cmd_stats(strategy)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
