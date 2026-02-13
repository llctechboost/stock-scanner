"""Trade Tracker - Manages trades by strategy"""
import json
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from config import TRADES_FILE, STRATEGIES

class Trade:
    def __init__(
        self,
        symbol: str,
        strategy: str,
        side: str,
        qty: float,
        entry_price: float,
        stop_loss: float = None,
        target: float = None,
        order_id: str = None,
        client_order_id: str = None,
        entry_date: str = None,
        exit_price: float = None,
        exit_date: str = None,
        status: str = "open",
        notes: str = ""
    ):
        self.symbol = symbol
        self.strategy = strategy
        self.side = side
        self.qty = qty
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target = target
        self.order_id = order_id
        self.client_order_id = client_order_id
        self.entry_date = entry_date or datetime.now().isoformat()
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.status = status
        self.notes = notes
    
    @property
    def pnl(self) -> float:
        """Calculate P&L"""
        if self.exit_price:
            if self.side == "buy":
                return (self.exit_price - self.entry_price) * self.qty
            else:
                return (self.entry_price - self.exit_price) * self.qty
        return 0.0
    
    @property
    def pnl_pct(self) -> float:
        """Calculate P&L percentage"""
        if self.exit_price and self.entry_price:
            if self.side == "buy":
                return ((self.exit_price - self.entry_price) / self.entry_price) * 100
            else:
                return ((self.entry_price - self.exit_price) / self.entry_price) * 100
        return 0.0
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "side": self.side,
            "qty": self.qty,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "entry_date": self.entry_date,
            "exit_price": self.exit_price,
            "exit_date": self.exit_date,
            "status": self.status,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "Trade":
        return cls(**d)


class TradeTracker:
    def __init__(self):
        self.trades: List[Trade] = []
        self._load()
    
    def _load(self):
        """Load trades from file"""
        if TRADES_FILE.exists():
            data = json.loads(TRADES_FILE.read_text())
            self.trades = [Trade.from_dict(t) for t in data]
    
    def _save(self):
        """Save trades to file"""
        data = [t.to_dict() for t in self.trades]
        TRADES_FILE.write_text(json.dumps(data, indent=2))
    
    def add_trade(self, trade: Trade):
        """Add a new trade"""
        self.trades.append(trade)
        self._save()
    
    def close_trade(self, symbol: str, exit_price: float, strategy: str = None):
        """Close an open trade"""
        for trade in self.trades:
            if trade.symbol == symbol and trade.status == "open":
                if strategy and trade.strategy != strategy:
                    continue
                trade.exit_price = exit_price
                trade.exit_date = datetime.now().isoformat()
                trade.status = "closed"
                self._save()
                return trade
        return None
    
    def get_open_trades(self, strategy: str = None) -> List[Trade]:
        """Get open trades, optionally filtered by strategy"""
        trades = [t for t in self.trades if t.status == "open"]
        if strategy:
            trades = [t for t in trades if t.strategy == strategy]
        return trades
    
    def get_closed_trades(self, strategy: str = None) -> List[Trade]:
        """Get closed trades, optionally filtered by strategy"""
        trades = [t for t in self.trades if t.status == "closed"]
        if strategy:
            trades = [t for t in trades if t.strategy == strategy]
        return trades
    
    def get_stats(self, strategy: str = None) -> dict:
        """Get trading stats, optionally filtered by strategy"""
        closed = self.get_closed_trades(strategy)
        if not closed:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0}
        
        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in closed)
        
        return {
            "trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(closed)) * 100 if closed else 0,
            "total_pnl": total_pnl,
            "avg_win": sum(t.pnl for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t.pnl for t in losses) / len(losses) if losses else 0
        }
    
    def summary(self) -> str:
        """Get a formatted summary"""
        lines = ["📊 **TRADING SUMMARY**\n"]
        
        # Overall stats
        stats = self.get_stats()
        lines.append(f"**Overall:** {stats['trades']} trades | {stats['win_rate']:.0f}% win rate | ${stats['total_pnl']:,.2f} P&L\n")
        
        # By strategy
        for strat, name in STRATEGIES.items():
            s = self.get_stats(strat)
            if s['trades'] > 0:
                lines.append(f"**{strat}** ({name}): {s['trades']} trades | {s['win_rate']:.0f}% | ${s['total_pnl']:,.2f}")
        
        # Open positions
        open_trades = self.get_open_trades()
        if open_trades:
            lines.append(f"\n**Open Positions:** {len(open_trades)}")
            for t in open_trades:
                lines.append(f"  • {t.symbol} ({t.strategy}): {t.qty} @ ${t.entry_price:.2f}")
        
        return "\n".join(lines)


# Singleton
tracker = TradeTracker()

if __name__ == "__main__":
    print(tracker.summary())
