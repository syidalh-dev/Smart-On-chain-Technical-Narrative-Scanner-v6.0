# smart_insights.py
# -*- coding: utf-8 -*-
"""
smart_insights.py
إضافات ذكية لتحليل السلوك والميديا للمشاريع الجديدة
"""

import requests
import time
import os

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
COINMARKETCAL_API_KEY = os.environ.get("COINMARKETCAL_API_KEY", "")

def get_holders_growth(contract_address, chain="eth"):
    try:
        if chain == "eth":
            api = "https://api.etherscan.io/api"
            apiparams = {"module":"token","action":"tokeninfo","contractaddress": contract_address, "apikey": ETHERSCAN_API_KEY}
        elif chain == "bsc":
            api = "https://api.bscscan.com/api"
            apiparams = {"module":"token","action":"tokeninfo","contractaddress": contract_address, "apikey": ETHERSCAN_API_KEY}
        else:
            return 0.0

        res = requests.get(api, params=apiparams, timeout=12)
        data = res.json() if res.status_code==200 else {}
        holders_now = int(data.get("result", {}).get("holders", 0) or 0)
        return 0.0 if holders_now==0 else float(holders_now)
    except Exception:
        return 0.0

def has_recent_partnerships(symbol):
    try:
        if not COINMARKETCAL_API_KEY:
            return False
        url = "https://developers.coinmarketcal.com/v1/events"
        headers = {"x-api-key": COINMARKETCAL_API_KEY}
        params = {"coins": symbol.lower(), "max": 5, "sortBy": "date"}
        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code != 200:
            return False
        events = res.json().get("body", []) or []
        for e in events:
            txt = (e.get("title","") + " " + e.get("description","")).lower()
            if any(k in txt for k in ["partnership","collaboration","integration","launch","announcement","upgrade"]):
                return True
        return False
    except Exception:
        return False

def detect_smart_money_flow(volume_now, volume_week_ago, price_change_7d):
    try:
        if (volume_week_ago is None) or (volume_week_ago == 0):
            return False
        growth = (volume_now / volume_week_ago)
        if growth >= 3.0 and (abs(price_change_7d) < 10):
            return True
        return False
    except Exception:
        return False
