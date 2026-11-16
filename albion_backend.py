#!/usr/bin/env python3
"""
ALBION Backend - Real market analysis API
Reads live prices from Yahoo Finance, computes technical indicators
(RSI, MACD, Moving Averages) across 4 timeframes, and returns
unanimous signals as JSON.

Endpoints:
  GET /api/health
  GET /api/analyse?market=forex&op=daytrade
  GET /api/markets

Run:  python3 albion_backend.py
Port: 8000 (or set PORT env var)
"""
import json, os, re, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request

# ── CONFIG ──────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8000))
CACHE_TTL = 300  # 5 minutes

# Markets and their instruments
MARKETS = {
    "forex": {
        "label": "Forex", "unit": "pairs", "count": 16,
        "instruments": [
            {"symbol":"GBPCHF=X","name":"GBP/CHF","type":"forex"},
            {"symbol":"EURCHF=X","name":"EUR/CHF","type":"forex"},
            {"symbol":"USDJPY=X","name":"USD/JPY","type":"forex"},
            {"symbol":"EURUSD=X","name":"EUR/USD","type":"forex"},
            {"symbol":"GBPUSD=X","name":"GBP/USD","type":"forex"},
            {"symbol":"AUDUSD=X","name":"AUD/USD","type":"forex"},
            {"symbol":"USDCAD=X","name":"USD/CAD","type":"forex"},
            {"symbol":"NZDUSD=X","name":"NZD/USD","type":"forex"},
            {"symbol":"EURGBP=X","name":"EUR/GBP","type":"forex"},
            {"symbol":"AUDJPY=X","name":"AUD/JPY","type":"forex"},
            {"symbol":"EURAUD=X","name":"EUR/AUD","type":"forex"},
            {"symbol":"GBPAUD=X","name":"GBP/AUD","type":"forex"},
            {"symbol":"USDCHF=X","name":"USD/CHF","type":"forex"},
            {"symbol":"EURJPY=X","name":"EUR/JPY","type":"forex"},
            {"symbol":"GBPJPY=X","name":"GBP/JPY","type":"forex"},
            {"symbol":"CADJPY=X","name":"CAD/JPY","type":"forex"},
        ]
    },
    "commodities": {
        "label": "Commodities", "unit": "instruments", "count": 12,
        "instruments": [
            {"symbol":"GC=F","name":"Gold (XAU/USD)","type":"commodity"},
            {"symbol":"SI=F","name":"Silver (XAG/USD)","type":"commodity"},
            {"symbol":"HG=F","name":"Copper (HGLD)","type":"commodity"},
            {"symbol":"PL=F","name":"Platinum (XPT/USD)","type":"commodity"},
            {"symbol":"PA=F","name":"Palladium (XPD/USD)","type":"commodity"},
            {"symbol":"ZC=F","name":"Corn","type":"commodity"},
            {"symbol":"ZW=F","name":"Wheat","type":"commodity"},
            {"symbol":"ZS=F","name":"Soybeans","type":"commodity"},
            {"symbol":"KC=F","name":"Coffee C","type":"commodity"},
            {"symbol":"CT=F","name":"Cotton No. 2","type":"commodity"},
            {"symbol":"LB=F","name":"Live Cattle","type":"commodity"},
            {"symbol":"LE=F","name":"Lean Hogs","type":"commodity"},
        ]
    },
    "indices": {
        "label": "Indices", "unit": "indices", "count": 14,
        "instruments": [
            {"symbol":"^NDX","name":"Nasdaq 100","type":"index"},
            {"symbol":"^GSPC","name":"S&P 500","type":"index"},
            {"symbol":"^DJI","name":"Dow Jones","type":"index"},
            {"symbol":"^FTSE","name":"FTSE 100","type":"index"},
            {"symbol":"^GDAXI","name":"DAX 40","type":"index"},
            {"symbol":"^FCHI","name":"CAC 40","type":"index"},
            {"symbol":"^STOXX50E","name":"Euro Stoxx 50","type":"index"},
            {"symbol":"^N225","name":"Nikkei 225","type":"index"},
            {"symbol":"^HSI","name":"Hang Seng","type":"index"},
            {"symbol":"^AXJO","name":"ASX 200","type":"index"},
            {"symbol":"^TSX","name":"TSX Composite","type":"index"},
            {"symbol":"^IXIC","name":"Nasdaq Composite","type":"index"},
            {"symbol":"^RUT","name":"Russell 2000","type":"index"},
            {"symbol":"^VIX","name":"VIX","type":"index"},
        ]
    },
    "futures": {
        "label": "Futures", "unit": "contracts", "count": 10,
        "instruments": [
            {"symbol":"CL=F","name":"Crude Oil WTI","type":"future"},
            {"symbol":"BZ=F","name":"Brent Crude","type":"future"},
            {"symbol":"NG=F","name":"Natural Gas","type":"future"},
            {"symbol":"RB=F","name":"RBOB Gasoline","type":"future"},
            {"symbol":"ZB=F","name":"US 10Y Bond","type":"future"},
            {"symbol":"ZN=F","name":"US 5Y Bond","type":"future"},
            {"symbol":"ZT=F","name":"US 2Y Bond","type":"future"},
            {"symbol":"6E=F","name":"Euro FX Futures","type":"future"},
            {"symbol":"6B=F","name":"British Pound Futures","type":"future"},
            {"symbol":"JY=F","name":"Japanese Yen Futures","type":"future"},
        ]
    },
    "stocks": {
        "label": "Stocks", "unit": "tickers", "count": 20,
        "instruments": [
            {"symbol":"AAPL","name":"Apple (AAPL)","type":"stock"},
            {"symbol":"MSFT","name":"Microsoft (MSFT)","type":"stock"},
            {"symbol":"GOOGL","name":"Alphabet (GOOGL)","type":"stock"},
            {"symbol":"AMZN","name":"Amazon (AMZN)","type":"stock"},
            {"symbol":"NVDA","name":"Nvidia (NVDA)","type":"stock"},
            {"symbol":"META","name":"Meta (META)","type":"stock"},
            {"symbol":"TSLA","name":"Tesla (TSLA)","type":"stock"},
            {"symbol":"BRK-B","name":"Berkshire Hathaway","type":"stock"},
            {"symbol":"JPM","name":"JPMorgan (JPM)","type":"stock"},
            {"symbol":"V","name":"Visa (V)","type":"stock"},
            {"symbol":"UNH","name":"UnitedHealth (UNH)","type":"stock"},
            {"symbol":"XOM","name":"Exxon Mobil (XOM)","type":"stock"},
            {"symbol":"LLY","name":"Eli Lilly (LLY)","type":"stock"},
            {"symbol":"AVGO","name":"Broadcom (AVGO)","type":"stock"},
            {"symbol":"MA","name":"Mastercard (MA)","type":"stock"},
            {"symbol":"COST","name":"Costco (COST)","type":"stock"},
            {"symbol":"HD","name":"Home Depot (HD)","type":"stock"},
            {"symbol":"PG","name":"Procter & Gamble","type":"stock"},
            {"symbol":"RR.L","name":"Rolls-Royce (RR.L)","type":"stock"},
            {"symbol":"SHEL.L","name":"Shell (SHEL.L)","type":"stock"},
        ]
    },
}

# Operation type -> timeframes to check
OP_TIMEFRAMES = {
    "daytrade": [
        ("5m",  "5 Min",  "1d"),
        ("15m", "15 Min", "5d"),
        ("1h",  "1 Hour", "1mo"),
        ("4h",  "4 Hour", "3mo"),
    ],
    "buyhold": [
        ("1d",  "Daily",     "3mo"),
        ("1wk", "Weekly",    "1y"),
        ("1mo", "Monthly",   "2y"),
        ("3mo", "Quarterly", "5y"),
    ],
    "binary": [
        ("1m",  "1 Min",  "5d"),
        ("5m",  "5 Min",  "1mo"),
        ("15m", "15 Min", "3mo"),
        ("30m", "30 Min", "6mo"),
    ],
}

# ── DATA FETCHING ───────────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()

def fetch_yahoo(symbol, interval, range_):
    """Fetch OHLC data from Yahoo Finance chart API."""
    key = f"{symbol}:{interval}:{range_}"
    with _cache_lock:
        if key in _cache:
            ts, data = _cache[key]
            if time.time() - ts < CACHE_TTL:
                return data
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(symbol)}?range={range_}&interval={interval}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = json.loads(r.read())
    result = raw["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    closes = [c for c in quote["close"] if c is not None]
    highs  = [h for h in quote["high"]  if h is not None]
    lows   = [l for l in quote["low"]   if l is not None]
    price  = result["meta"].get("regularMarketPrice")
    prev   = result["meta"].get("chartPreviousClose")
    data = {"closes": closes, "highs": highs, "lows": lows, "price": price, "prev": prev}
    with _cache_lock:
        _cache[key] = (time.time(), data)
    return data

# ── TECHNICAL INDICATORS ────────────────────────────────────────
def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period

def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e

def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period-1) + gains[i]) / period
        avg_l = (avg_l * (period-1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))

def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None, None
    def ema_series(vals, p):
        if len(vals) < p: return []
        k = 2/(p+1)
        e = sum(vals[:p])/p
        out = [e]
        for v in vals[p:]:
            e = v*k + e*(1-k)
            out.append(e)
        return out
    ef = ema_series(closes, fast)
    es = ema_series(closes, slow)
    if len(ef) < len(es) or len(es) < signal:
        return None, None
    # align
    offset = len(ef) - len(es)
    ef_aligned = ef[offset:]
    macd_line = [a - b for a, b in zip(ef_aligned, es)]
    sig_line = ema_series(macd_line, signal)
    if not sig_line:
        return None, None
    return macd_line[-1], sig_line[-1]

def analyse_timeframe(closes, highs, lows):
    """Return a signal dict for one timeframe."""
    if len(closes) < 20:
        return {"signal": "neutral", "confidence": 0, "details": {}}
    
    price = closes[-1]
    ma20 = sma(closes, 20)
    ma50 = sma(closes, 50) if len(closes) >= 50 else sma(closes, min(50, len(closes)))
    r = rsi(closes, 14)
    m, s = macd(closes)
    
    score = 0
    details = {}
    
    # MA position
    if ma20 and price > ma20:
        score += 1
        details["ma20"] = "above"
    elif ma20:
        score -= 1
        details["ma20"] = "below"
    
    # MA crossover
    if ma20 and ma50:
        if ma20 > ma50:
            score += 1
            details["ma_cross"] = "bullish"
        else:
            score -= 1
            details["ma_cross"] = "bearish"
    
    # RSI
    if r is not None:
        details["rsi"] = round(r, 1)
        if r < 30:
            score += 1  # oversold -> potential buy
        elif r > 70:
            score -= 1  # overbought -> potential sell
        elif r > 50:
            score += 0.5
        else:
            score -= 0.5
    
    # MACD
    if m is not None and s is not None:
        details["macd"] = "bullish" if m > s else "bearish"
        if m > s:
            score += 1
        else:
            score -= 1
    
    # Momentum (last 5 candles)
    if len(closes) >= 6:
        mom = (closes[-1] - closes[-6]) / closes[-6] * 100
        details["momentum_5"] = round(mom, 2)
        if mom > 0.5:
            score += 0.5
        elif mom < -0.5:
            score -= 0.5
    
    # Determine signal
    max_score = 5
    ratio = score / max_score
    if ratio >= 0.6:
        sig = "strong_buy"
    elif ratio >= 0.2:
        sig = "buy"
    elif ratio <= -0.6:
        sig = "strong_sell"
    elif ratio <= -0.2:
        sig = "sell"
    else:
        sig = "neutral"
    
    return {"signal": sig, "score": round(score, 1), "details": details}

# ── MAIN ANALYSIS ───────────────────────────────────────────────
def analyse_market(market_key, op_type):
    market = MARKETS[market_key]
    timeframes = OP_TIMEFRAMES[op_type]
    results = []
    errors = []
    
    for inst in market["instruments"]:
        sym = inst["symbol"]
        tf_results = []
        ok = True
        for interval, label, range_ in timeframes:
            try:
                d = fetch_yahoo(sym, interval, range_)
                tf_res = analyse_timeframe(d["closes"], d["highs"], d["lows"])
                tf_results.append({"label": label, **tf_res})
            except Exception as e:
                errors.append(f"{sym}/{interval}: {e}")
                ok = False
                tf_results.append({"label": label, "signal": "error", "score": 0, "details": {}})
        
        if not ok:
            continue
        
        # Check unanimity: all 4 must be buy-side or all sell-side
        signals = [t["signal"] for t in tf_results]
        buy_signals = {"buy", "strong_buy"}
        sell_signals = {"sell", "strong_sell"}
        
        all_buy = all(s in buy_signals for s in signals)
        all_sell = all(s in sell_signals for s in signals)
        
        if all_buy:
            overall = "STRONG BUY" if all(s == "strong_buy" for s in signals) else "BUY"
            direction = "buy"
        elif all_sell:
            overall = "STRONG SELL" if all(s == "strong_sell" for s in signals) else "SELL"
            direction = "sell"
        else:
            overall = "MIXED"
            direction = "neutral"
        
        # Price change
        try:
            d1 = fetch_yahoo(sym, timeframes[0][0], timeframes[0][2])
            price = d1["price"]
            prev = d1["prev"]
            change_pct = ((price - prev) / prev * 100) if prev else 0
        except:
            price = None
            change_pct = 0
        
        results.append({
            "symbol": sym,
            "name": inst["name"],
            "price": round(price, 4) if price else None,
            "change_pct": round(change_pct, 2),
            "overall": overall,
            "direction": direction,
            "timeframes": tf_results,
            "aligned": direction != "neutral",
        })
    
    # Sort: aligned first, then by absolute score
    results.sort(key=lambda x: (not x["aligned"], -abs(x["timeframes"][0].get("score", 0))))
    
    return {
        "market": market_key,
        "market_label": market["label"],
        "operation": op_type,
        "timeframes_checked": [t[1] for t in timeframes],
        "total_instruments": market["count"],
        "signals_found": sum(1 for r in results if r["aligned"]),
        "results": results[:10],  # top 10
        "errors": errors[:5],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

# ── NEWS (simple keyword search via RSS) ────────────────────────
def get_news(market_key):
    """Fetch recent financial news headlines from free RSS feeds."""
    feeds = [
        ("Reuters", "https://feeds.reuters.com/reuters/businessNews"),
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ]
    articles = []
    for source, url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                content = r.read().decode("utf-8", errors="ignore")
            # Parse RSS items (simple regex)
            items = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
            for item in items[:3]:
                title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
                link_m = re.search(r"<link>(.*?)</link>", item)
                desc_m = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", item, re.DOTALL)
                if title_m:
                    articles.append({
                        "source": source,
                        "title": title_m.group(1).strip()[:120],
                        "url": link_m.group(1).strip() if link_m else "#",
                        "excerpt": re.sub(r"<[^>]+>", "", desc_m.group(1)).strip()[:200] if desc_m else "",
                    })
        except:
            pass
    return articles[:6]

# ── HTTP HANDLER ────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def _json(self, code, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)
        
        if path == "/api/health":
            self._json(200, {"status": "ok", "service": "ALBION Backend", "time": time.strftime("%H:%M:%S UTC", time.gmtime())})
        
        elif path == "/api/markets":
            self._json(200, {k: {"label": v["label"], "count": v["count"], "instruments": len(v["instruments"])} for k, v in MARKETS.items()})
        
        elif path == "/api/analyse":
            market = params.get("market", ["forex"])[0]
            op = params.get("op", ["daytrade"])[0]
            if market not in MARKETS:
                self._json(400, {"error": f"Unknown market: {market}. Use: {list(MARKETS.keys())}"})
                return
            if op not in OP_TIMEFRAMES:
                self._json(400, {"error": f"Unknown operation: {op}. Use: {list(OP_TIMEFRAMES.keys())}"})
                return
            try:
                t0 = time.time()
                result = analyse_market(market, op)
                result["news"] = get_news(market)
                result["elapsed_s"] = round(time.time() - t0, 1)
                self._json(200, result)
            except Exception as e:
                self._json(500, {"error": str(e)})
        
        elif path == "/api/news":
            market = params.get("market", ["forex"])[0]
            self._json(200, {"news": get_news(market)})
        
        else:
            self._json(404, {"error": "Not found. Use /api/health, /api/markets, /api/analyse?market=X&op=Y"})
    
    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {fmt % args}")

if __name__ == "__main__":
    print(f"ALBION Backend starting on port {PORT}")
    print(f"  Health:  http://localhost:{PORT}/api/health")
    print(f"  Markets: http://localhost:{PORT}/api/markets")
    print(f"  Analyse: http://localhost:{PORT}/api/analyse?market=forex&op=daytrade")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
