"""
BybitTestnetTrader — Testnet order execution module for Bybit demo account.
Uses testnet endpoint: https://api-testnet.bybit.com
"""
import hashlib
import hmac
import json
import time
from typing import Optional
import requests
from datetime import datetime, timezone


class BybitTestnetTrader:
    """Execute trades on Bybit testnet (demo account)."""
    
    def __init__(self, api_key: str, api_secret: str):
        """
        Initialize Bybit testnet trader.
        
        Args:
            api_key: Demo account API key
            api_secret: Demo account API secret
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api-testnet.bybit.com"
        self.session = requests.Session()
    
    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC SHA256 signature for request."""
        return hmac.new(
            self.api_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _make_request(self, method: str, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Make authenticated request to Bybit testnet API.
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint (e.g., "/v5/order/create")
            params: Query or body parameters
        
        Returns:
            API response as dict
        """
        url = self.base_url + endpoint
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        
        # Build payload string for signature
        if method == "POST":
            payload = json.dumps(params) if params else ""
            signature = self._generate_signature(timestamp + self.api_key + recv_window + payload)
            headers = {
                "X-BAPI-SIGN": signature,
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
                "Content-Type": "application/json",
            }
            response = self.session.post(url, json=params, headers=headers, timeout=10)
        else:  # GET
            query_string = "&".join(
                [f"{k}={v}" for k, v in (params or {}).items()]
            ) if params else ""
            signature = self._generate_signature(timestamp + self.api_key + recv_window + query_string)
            headers = {
                "X-BAPI-SIGN": signature,
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
            }
            response = self.session.get(url, params=params, headers=headers, timeout=10)
        
        return response.json()
    
    def place_market_buy(
        self,
        symbol: str,
        qty: float,
        tp: float,
        sl: float,
    ) -> dict:
        """
        Submit market BUY order to testnet.
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT")
            qty: Order quantity
            tp: Take profit price (absolute)
            sl: Stop loss price (absolute)
        
        Returns:
            {
                "order_id": str,
                "entry_price": float,
                "qty": float,
                "status": "Pending"|"Filled"|"Error",
                "error": Optional[str],
            }
        """
        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": "Buy",
            "orderType": "Market",
            "qty": str(qty),
            "takeProfit": str(round(tp, 6)),
            "stopLoss": str(round(sl, 6)),
            "timeInForce": "IOC",  # Immediate or Cancel
        }
        
        try:
            response = self._make_request("POST", "/v5/order/create", payload)
            
            if response.get("retCode") == 0:
                data = response.get("result", {})
                return {
                    "order_id": data.get("orderId"),
                    "entry_price": None,  # Market order; price filled at execution
                    "qty": qty,
                    "status": "Pending",
                    "error": None,
                }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                return {
                    "order_id": None,
                    "entry_price": None,
                    "qty": qty,
                    "status": "Error",
                    "error": error_msg,
                }
        except Exception as e:
            return {
                "order_id": None,
                "entry_price": None,
                "qty": qty,
                "status": "Error",
                "error": str(e),
            }
    
    def place_market_sell(self, symbol: str, qty: float) -> dict:
        """
        Submit market SELL order to testnet.
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT")
            qty: Order quantity
        
        Returns:
            {
                "order_id": str,
                "exit_price": float,
                "qty": float,
                "status": "Pending"|"Filled"|"Error",
                "error": Optional[str],
            }
        """
        payload = {
            "category": "linear",
            "symbol": symbol,
            "side": "Sell",
            "orderType": "Market",
            "qty": str(qty),
            "timeInForce": "IOC",
        }
        
        try:
            response = self._make_request("POST", "/v5/order/create", payload)
            
            if response.get("retCode") == 0:
                data = response.get("result", {})
                return {
                    "order_id": data.get("orderId"),
                    "exit_price": None,  # Market order; price filled at execution
                    "qty": qty,
                    "status": "Pending",
                    "error": None,
                }
            else:
                error_msg = response.get("retMsg", "Unknown error")
                return {
                    "order_id": None,
                    "exit_price": None,
                    "qty": qty,
                    "status": "Error",
                    "error": error_msg,
                }
        except Exception as e:
            return {
                "order_id": None,
                "exit_price": None,
                "qty": qty,
                "status": "Error",
                "error": str(e),
            }
    
    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """
        Query testnet for open orders.
        
        Args:
            symbol: Optional filter by symbol
        
        Returns:
            List of open orders [{order_id, symbol, qty, side, status, ...}]
        """
        params = {
            "category": "linear",
            "settleCoin": "USDT",
        }
        if symbol:
            params["symbol"] = symbol
        
        try:
            response = self._make_request("GET", "/v5/order/realtime", params)
            
            if response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                return [
                    {
                        "order_id": o.get("orderId"),
                        "symbol": o.get("symbol"),
                        "qty": float(o.get("qty", 0)),
                        "side": o.get("side"),
                        "status": o.get("orderStatus"),
                        "price": float(o.get("price", 0)) if o.get("price") else None,
                    }
                    for o in orders
                ]
            else:
                return []
        except Exception:
            return []
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel order by ID.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair (required by API)
        
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
        }
        
        try:
            response = self._make_request("POST", "/v5/order/cancel", payload)
            return response.get("retCode") == 0
        except Exception:
            return False
    
    def get_order_status(self, order_id: str, symbol: str) -> dict:
        """
        Get order execution details (fill price, status, etc).
        
        Args:
            order_id: Order ID to query
            symbol: Trading pair
        
        Returns:
            {
                "order_id": str,
                "symbol": str,
                "status": str,
                "avg_price": float,
                "qty": float,
                "filled_qty": float,
            }
        """
        params = {
            "category": "linear",
            "orderId": order_id,
            "symbol": symbol,
        }
        
        try:
            response = self._make_request("GET", "/v5/order/realtime", params)
            
            if response.get("retCode") == 0:
                orders = response.get("result", {}).get("list", [])
                if orders:
                    o = orders[0]
                    return {
                        "order_id": o.get("orderId"),
                        "symbol": o.get("symbol"),
                        "status": o.get("orderStatus"),
                        "avg_price": float(o.get("avgPrice", 0)) if o.get("avgPrice") else 0,
                        "qty": float(o.get("qty", 0)),
                        "filled_qty": float(o.get("cumExecQty", 0)),
                    }
            return {}
        except Exception:
            return {}
