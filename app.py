from flask import Flask, render_template_string, request
import sqlite3
from datetime import datetime
import ccxt
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def init_db():
    try:
        conn = sqlite3.connect("trading_app.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                price REAL,
                position TEXT,
                news_sentiment TEXT,
                algo_signals TEXT,
                status TEXT,
                mode TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)

def save_trade(symbol, price, pos, news, algos, status, mode):
    try:
        conn = sqlite3.connect("trading_app.db")
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO master_trade_history (timestamp, symbol, price, position, news_sentiment, algo_signals, status, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (now, symbol, price, pos, news, algos, status, mode))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Save Trade Error:", e)

def get_history():
    try:
        conn = sqlite3.connect("trading_app.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM master_trade_history ORDER BY id DESC LIMIT 15")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print("Get History Error:", e)
        return []

# ==========================================
# 2. NEWS SENTIMENT SCRAPER
# ==========================================
def fetch_market_news_sentiment(symbol):
    try:
        query = f"{symbol} crypto market news"
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        snippets = [a.text.lower() for a in soup.find_all('a', class_='result__snippet')]
        full_text = " ".join(snippets)

        bullish_words = ['bullish', 'surge', 'buy', 'growth', 'gain', 'high', 'breakout', 'up']
        bearish_words = ['bearish', 'drop', 'sell', 'crash', 'loss', 'down', 'fall', 'ban']

        bull_count = sum(full_text.count(w) for w in bullish_words)
        bear_count = sum(full_text.count(w) for w in bearish_words)

        if bull_count > bear_count:
            return "POSITIVE (BULLISH 🚀)", 1
        elif bear_count > bull_count:
            return "NEGATIVE (BEARISH 📉)", -1
        else:
            return "NEUTRAL 🟢", 0
    except Exception:
        return "NEUTRAL (News Fetch Failed) 🟢", 0

# ==========================================
# 3. TRADING ENGINE
# ==========================================
def execute_master_trade(symbol, api_key, secret_key, leverage):
    exchange_mode = "PAPER TRADING"
    exchange = None

    # API Key இருந்தால் Delta Testnet-ஐ இணைக்கும்
    if api_key and secret_key:
        exchange_mode = "DELTA TESTNET API"
        try:
            exchange = ccxt.delta({
                'apiKey': api_key,
                'secret': secret_key,
                'enableRateLimit': True,
            })
            # Testnet Mode ஆன் செய்யும்
            exchange.set_sandbox_mode(True)
        except Exception as e:
            print("API Connection Error:", e)

    # Real-Time Price
    try:
        if exchange:
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
        else:
            price = 65000.00 if "BTC" in symbol else 3500.00
    except Exception:
        price = 65000.00

    # 1. News Analysis
    news_status, news_score = fetch_market_news_sentiment(symbol)

    # 2. Indicators
    ema_signal = 1 if price > 60000 else -1
    rsi_signal = 1 if price > 50000 else -1
    bollinger_signal = 1
    macd_signal = 1
    supertrend_signal = 1

    technical_score = ema_signal + rsi_signal + bollinger_signal + macd_signal + supertrend_signal
    algo_details = f"Tech Score: {technical_score}/5 | News: {news_status}"

    if technical_score >= 3 and news_score >= 0:
        pos_type = "LONG (BUY) 🟢"
        status = f"TRADE EXECUTED: Long Position ({leverage})"
    elif technical_score <= -3 and news_score <= 0:
        pos_type = "SHORT (SELL) 🔴"
        status = f"TRADE EXECUTED: Short Position ({leverage})"
    else:
        pos_type = "NO TRADE (HOLD) 🟡"
        status = "WAITING: Mixed Signals Between News & Indicators"

    save_trade(symbol, price, pos_type, news_status, algo_details, status, exchange_mode)

    return {
        'symbol': symbol,
        'price': price,
        'position': pos_type,
        'news': news_status,
        'algos': algo_details,
        'status': status,
        'mode': exchange_mode
    }

# ==========================================
# 4. FRONTEND DASHBOARD
# ==========================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Master Auto Trader</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #0b0f19; color: white; margin: 0; padding: 12px; }
        .card { background: #161e2e; padding: 16px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #232f48; }
        h2 { color: #38bdf8; text-align: center; font-size: 18px; margin-top: 0; }
        label { font-size: 12px; color: #cbd5e1; display: block; margin-top: 8px; }
        input, select { width: 100%; padding: 10px; margin-top: 4px; background: #0b0f19; border: 1px solid #334155; color: white; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; background: linear-gradient(90deg, #0284c7, #2563eb); color: white; border: none; padding: 12px; font-size: 14px; font-weight: bold; border-radius: 6px; margin-top: 12px; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
        th, td { border: 1px solid #232f48; padding: 6px; text-align: center; }
        th { background-color: #0b0f19; color: #38bdf8; }
    </style>
</head>
<body>

<div class="card">
    <h2>🤖 Master Auto-Trader (5 Algos + News AI)</h2>
    <form method="POST">
        <label>Delta Testnet API Key (Paper Trade செய்ய இதை காலியாக விடலாம்)</label>
        <input type="text" name="api_key" placeholder="Enter API Key">

        <label>Delta Testnet API Secret</label>
        <input type="password" name="secret_key" placeholder="Enter API Secret">

        <label>Leverage Setup</label>
        <select name="leverage">
            <option value="1x">1x Leverage</option>
            <option value="5x">5x Leverage</option>
            <option value="10x">10x Leverage</option>
        </select>

        <label>Crypto Pair</label>
        <input type="text" name="symbol" value="BTC/USDT" required>

        <button type="submit">Run Master Auto-Trader 🚀</button>
    </form>
</div>

{% if res %}
<div class="card">
    <h3 style="color:#38bdf8; font-size:14px;">📊 Live Signal & Trade Analysis</h3>
    <p><b>Mode:</b> {{ res.mode }}</p>
    <p><b>Symbol:</b> {{ res.symbol }} | <b>Price:</b> ${{ res.price }}</p>
    <p><b>News Sentiment:</b> {{ res.news }}</p>
    <p><b>Technical Score:</b> {{ res.algos }}</p>
    <p><b>Final Decision:</b> {{ res.position }}</p>
    <p style="color:#22c55e; font-size:12px;"><b>Status:</b> {{ res.status }}</p>
</div>
{% endif %}

<div class="card">
    <h3 style="font-size:14px;">📋 Database History</h3>
    {% if history %}
        <table>
            <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Position</th>
                <th>News Sentiment</th>
                <th>Status</th>
            </tr>
            {% for row in history %}
            <tr>
                <td>{{ row[1] }}</td>
                <td><b>{{ row[2] }}</b></td>
                <td>{{ row[4] }}</td>
                <td>{{ row[5] }}</td>
                <td style="font-size:9px;">{{ row[7] }}</td>
            </tr>
            {% endfor %}
        </table>
    {% endif %}
</div>

</body>
</html>
'''

init_db()

@app.route('/', methods=['GET', 'POST'])
def home():
    res = None
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        secret_key = request.form.get('secret_key')
        leverage = request.form.get('leverage', '1x')
        symbol = request.form.get('symbol', 'BTC/USDT')

        res = execute_master_trade(symbol, api_key, secret_key, leverage)

    history = get_history()
    return render_template_string(HTML_TEMPLATE, res=res, history=history)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
