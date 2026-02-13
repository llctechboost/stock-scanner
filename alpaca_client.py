"""Alpaca API Client"""
import requests
from typing import Optional
from config import ALPACA_BASE_URL, ALPACA_KEY, ALPACA_SECRET

class AlpacaClient:
    def __init__(self):
        self.base_url = ALPACA_BASE_URL
        self.headers = {
            "APCA-API-KEY-ID": ALPACA_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET,
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        resp = requests.request(method, url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json() if resp.text else {}
    
    def get_account(self) -> dict:
        """Get account info (balance, buying power, etc)"""
        return self._request("GET", "/account")
    
    def get_positions(self) -> list:
        """Get all open positions"""
        return self._request("GET", "/positions")
    
    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position for specific symbol"""
        try:
            return self._request("GET", f"/positions/{symbol}")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def get_orders(self, status: str = "open") -> list:
        """Get orders by status (open, closed, all)"""
        return self._request("GET", f"/orders?status={status}")
    
    def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,  # "buy" or "sell"
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: float = None,
        stop_price: float = None,
        client_order_id: str = None
    ) -> dict:
        """Place an order"""
        data = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force
        }
        if limit_price:
            data["limit_price"] = str(limit_price)
        if stop_price:
            data["stop_price"] = str(stop_price)
        if client_order_id:
            data["client_order_id"] = client_order_id
        
        return self._request("POST", "/orders", data)
    
    def cancel_order(self, order_id: str) -> dict:
        """Cancel an order"""
        return self._request("DELETE", f"/orders/{order_id}")
    
    def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 100) -> list:
        """Get price bars (uses data API)"""
        data_url = "https://data.alpaca.markets/v2"
        url = f"{data_url}/stocks/{symbol}/bars?timeframe={timeframe}&limit={limit}"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("bars", [])
    
    def get_quote(self, symbol: str) -> dict:
        """Get latest quote"""
        data_url = "https://data.alpaca.markets/v2"
        url = f"{data_url}/stocks/{symbol}/quotes/latest"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("quote", {})


# Singleton
client = AlpacaClient()

if __name__ == "__main__":
    # Quick test
    acct = client.get_account()
    print(f"Account: ${float(acct['equity']):,.2f}")
    print(f"Buying Power: ${float(acct['buying_power']):,.2f}")
