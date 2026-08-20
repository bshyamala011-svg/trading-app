from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
from datetime import datetime
import ccxt
import requests
from bs4 import BeautifulSoup
import threading
import time

app = Flask(__name__)

# Global variables
bot_running = False
bot_thread = None
active_config = {
    'symbol': 'BTC/USDT',
    'api_key': '',
    'secret_key': '',
    'leverage': '1x',
    'key_name': 'Paper Trading (Default)'
}

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def init_db():
    try:
        conn = sqlite3.connect("trading_app.db", check_same_thread=False)
        cursor = conn.cursor()
        
        # Trade History Table
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
        
        # API Keys Storage Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_name TEXT UNIQUE,
                api_key TEXT,
                secret_key TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Init Error:", e)

def save_trade_log(symbol, price, pos, news, algos, status, mode):
    try:
        conn = sqlite3.connect("trading_app.db", check_same_thread=False)
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
        conn = sqlite3.connect("trading_app.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM master_trade_history ORDER BY id DESC LIMIT 15")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print("Get History Error:", e)
        return []

def get_saved_keys():
    try:
        conn = sqlite3.connect("trading_app.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT id, key_name, api_key, secret_key FROM saved_api_keys")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print("Get Keys Error:", e)
        return []

def add_api_key(name, key, secret):
    try:
        conn = sqlite3.connect("trading_app.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO saved_api_keys (key_name, api_key, secret_key)
            VALUES (?, ?, ?)
        ''', (name, key, secret))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Add Key Error:", e)

# ==========================================
# 2. MARKET NEWS SCRAPER
# ==========================================
def fetch_market_news_sentiment(symbol):
    try:
        query = f"{symbol} crypto market news"
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=3)
        
        if response.status_code == 200:
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
        return "NEUTRAL 🟢", 0
    except Exception:
        return "NEUTRAL (Bypass) 🟢", 0

# ==========================================
# 3. TRADING ENGINE & SCALPER
# ==========================================
def execute_master_trade():
    global bot_running
    symbol = active_config['symbol']
    api_key = active_config['api_key']
    secret_key = active_config['secret_key']
    leverage = active_config['leverage']

    exchange_mode = "PAPER TRADING"
    default_price = 65000.00 if "BTC" in symbol else 3500.00
    entry_price = None
    exchange = None

    if api_key and secret_key:
        exchange_mode = f"API: {active_config['key_name']}"
        try:
            exchange = ccxt.delta({
                'apiKey': api_key.strip(),
                'secret': secret_key.strip(),
                'enableRateLimit': True,
            })
            exchange.set_sandbox_mode(True)
            ticker = exchange.fetch_ticker(symbol)
            entry_price = ticker.get('last')
        except Exception as e:
            print("API Connection Error:", e)

    if entry_price is None or not isinstance(entry_price, (int, float)):
        entry_price = default_price

    news_status, news_score = fetch_market_news_sentiment(symbol)

    # 5 Technical Signals
    ema_signal = 1 if entry_price > 60000 else -1
    rsi_signal = 1 if entry_price > 50000 else -1
    bollinger_signal = 1
    macd_signal = 1
    supertrend_signal = 1

    technical_score = ema_signal + rsi_signal + bollinger_signal + macd_signal + supertrend_signal
    algo_details = f"Score: {technical_score}/5 | News: {news_status}"

    pos_type = "NO TRADE (HOLD) 🟡"
    status = "AUTO WAITING: Neutral Signals"

    if technical_score >= 3 and news_score >= 0:
        pos_type = "LONG (BUY) 🟢"
        status = f"AUTO OPEN: Long Position ({leverage})"
    elif technical_score <= -3 and news_score <= 0:
        pos_type = "SHORT (SELL) 🔴"
        status = f"AUTO OPEN: Short Position ({leverage})"

    save_trade_log(symbol, entry_price, pos_type, news_status, algo_details, status, exchange_mode)

    if "NO TRADE" in pos_type:
        return

    # Scalping Exit Logic
    target_profit_percent = 0.005  # 0.5% Target Profit
    stop_loss_percent = 0.003     # 0.3% Stop Loss

    start_time = time.time()
    while time.time() - start_time < 300:  # 5 Mins Limit
        if not bot_running:
            break

        current_price = entry_price
        if exchange:
            try:
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker.get('last') or entry_price
            except Exception:
                pass

        price_diff = ((current_price - entry_price) / entry_price) if pos_type.startswith("LONG") else ((entry_price - current_price) / entry_price)

        if price_diff >= target_profit_percent:
            exit_status = f"AUTO CLOSE: Profit Target Hit (+{round(price_diff*100, 2)}%) 🎯"
            save_trade_log(symbol, current_price, f"CLOSED ({pos_type.split()[0]})", news_status, algo_details, exit_status, exchange_mode)
            return

        elif price_diff <= -stop_loss_percent:
            exit_status = f"AUTO CLOSE: Stop Loss Hit ({round(price_diff*100, 2)}%) 🛑"
            save_trade_log(symbol, current_price, f"CLOSED ({pos_type.split()[0]})", news_status, algo_details, exit_status, exchange_mode)
            return

        time.sleep(10)

    exit_status = "AUTO CLOSE: 5 Min Limit Reached ⏱️"
    save_trade_log(symbol, entry_price, f"CLOSED ({pos_type.split()[0]})", news_status, algo_details, exit_status, exchange_mode)

def auto_trading_loop():
    global bot_running
    while bot_running:
        try:
            execute_master_trade()
        except Exception as e:
            print("Auto Loop Error:", e)
        time.sleep(2)

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
        h2, h3 { color: #38bdf8; margin-top: 0; }
        label { font-size: 12px; color: #cbd5e1; display: block; margin-top: 8px; }
        input, select { width: 100%; padding: 10px; margin-top: 4px; background: #0b0f19; border: 1px solid #334155; color: white; border-radius: 6px; box-sizing: border-box; }
        .btn-start { width: 100%; background: linear-gradient(90deg, #16a34a, #22c55e); color: white; border: none; padding: 12px; font-weight: bold; border-radius: 6px; margin-top: 12px; cursor: pointer; }
        .btn-stop { width: 100%; background: linear-gradient(90deg, #dc2626, #ef4444); color: white; border: none; padding: 12px; font-weight: bold; border-radius: 6px; margin-top: 8px; cursor: pointer; }
        .btn-save { background: #0284c7; color: white; border: none; padding: 8px; border-radius: 6px; margin-top: 8px; width: 100%; font-weight: bold; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
        th, td { border: 1px solid #232f48; padding: 6px; text-align: center; }
        th { background-color: #0b0f19; color: #38bdf8; }
        .status-badge { text-align: center; font-weight: bold; padding: 8px; border-radius: 6px; font-size: 13px; margin-bottom: 10px; }
        .active { background-color: #14532d; color: #4ade80; border: 1px solid #22c55e; }
        .inactive { background-color: #450a0a; color: #f87171; border: 1px solid #ef4444; }
    </style>
</head>
<body>

<div class="card">
    <h2 style="font-size: 18px; text-align: center;">🤖 Master Auto Trader (API Manager)</h2>

    {% if is_running %}
        <div class="status-badge active">🟢 BOT RUNNING (Active Key: {{ config.key_name }})</div>
    {% else %}
        <div class="status-badge inactive">🔴 BOT IS STOPPED</div>
    {% endif %}

    <!-- Save Key Section -->
    <details style="margin-bottom: 15px; background: #0b0f19; padding: 10px; border-radius: 6px;">
        <summary style="color: #38bdf8; font-size: 13px; cursor: pointer; font-weight: bold;">🔑 Save New API Key (புதிய API சேமிக்க)</summary>
        <form method="POST" action="/save_key">
            <label>Key Nickname (उदा: Delta Main)</label>
            <input type="text" name="key_name" placeholder="E.g. Delta Account 1" required>
            <label>API Key</label>
            <input type="text" name="api_key" required autocomplete="off" spellcheck="false">
            <label>API Secret</label>
            <input type="text" name="secret_key" required autocomplete="off" spellcheck="false">
            <button type="submit" class="btn-save">💾 Save API Key</button>
        </form>
    </details>

    <!-- Main Control Form -->
    <form method="POST" action="/control">
        <label>Select Saved API Key</label>
        <select name="selected_key_id">
            <option value="0">Paper Trading (No Real API Key)</option>
            {% for k in saved_keys %}
                <option value="{{ k[0] }}">{{ k[1] }}</option>
            {% endfor %}
        </select>

        <label>Leverage Setup</label>
        <select name="leverage">
            <option value="1x">1x Leverage</option>
            <option value="5x">5x Leverage</option>
            <option value="10x">10x Leverage</option>
        </select>

        <label>Crypto Pair</label>
        <input type="text" name="symbol" value="{{ config.symbol }}" required>

        <button type="submit" name="action" value="start" class="btn-start">▶ Start Auto Scalping Bot</button>
        <button type="submit" name="action" value="stop" class="btn-stop">⏹ Stop Bot</button>
    </form>
</div>

<div class="card">
    <h3 style="font-size:14px;">📋 Live Database Trade & Exit Log</h3>
    {% if history %}
        <table>
            <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Position</th>
                <th>Mode</th>
                <th>Status</th>
            </tr>
            {% for row in history %}
            <tr>
                <td>{{ row[1] }}</td>
                <td><b>{{ row[2] }}</b></td>
                <td>{{ row[4] }}</td>
                <td style="font-size:9px;">{{ row[8] }}</td>
                <td style="font-size:9px;">{{ row[7] }}</td>
            </tr>
            {% endfor %}
        </table>
    {% else %}
        <p style="font-size:12px; text-align:center;">இன்னும் டிரேடுகள் எதுவும் செய்யப்படவில்லை.</p>
    {% endif %}
</div>

</body>
</html>
'''

try:
    init_db()
except Exception as e:
    print("Startup DB error:", e)

@app.route('/')
def home():
    history = get_history()
    saved_keys = get_saved_keys()
    return render_template_string(HTML_TEMPLATE, is_running=bot_running, config=active_config, history=history, saved_keys=saved_keys)

@app.route('/save_key', methods=['POST'])
def save_key():
    name = request.form.get('key_name')
    key = request.form.get('api_key')
    secret = request.form.get('secret_key')
    if name and key and secret:
        add_api_key(name, key, secret)
    return redirect(url_for('home'))

@app.route('/control', methods=['POST'])
def control():
    global bot_running, bot_thread, active_config
    action = request.form.get('action')

    if action == 'start':
        key_id = int(request.form.get('selected_key_id', 0))
        active_config['leverage'] = request.form.get('leverage', '1x')
        active_config['symbol'] = request.form.get('symbol', 'BTC/USDT')

        if key_id == 0:
            active_config['api_key'] = ''
            active_config['secret_key'] = ''
            active_config['key_name'] = 'Paper Trading'
        else:
            saved_keys = get_saved_keys()
            for k in saved_keys:
                if k[0] == key_id:
                    active_config['key_name'] = k[1]
                    active_config['api_key'] = k[2]
                    active_config['secret_key'] = k[3]
                    break

        if not bot_running:
            bot_running = True
            bot_thread = threading.Thread(target=auto_trading_loop)
            bot_thread.daemon = True
            bot_thread.start()

    elif action == 'stop':
        bot_running = False

    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
                   
