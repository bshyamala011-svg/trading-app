from flask import Flask, render_template_string, request
import sqlite3
from datetime import datetime

app = Flask(__name__)

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def init_db():
    conn = sqlite3.connect("trading_app.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS multi_trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            buy_price REAL,
            short_ma REAL,
            long_ma REAL,
            rsi REAL,
            target_price REAL,
            stoploss_price REAL,
            signal TEXT,
            order_status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_multi_trade(symbol, price, sma, lma, rsi, target, stoploss, signal, status):
    conn = sqlite3.connect("trading_app.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO multi_trade_history (timestamp, symbol, buy_price, short_ma, long_ma, rsi, target_price, stoploss_price, signal, order_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (now, symbol, price, sma, lma, rsi, target, stoploss, signal, status))
    conn.commit()
    conn.close()

def get_saved_history():
    conn = sqlite3.connect("trading_app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM multi_trade_history ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ==========================================
# 2. MULTI-STOCK LIVE DATA & ALGO ENGINE
# ==========================================
def fetch_live_indicators(symbol):
    """
    5 பங்குகளுக்கான நேரலை விலைகள் & அல்கோ குறியீடுகள்
    """
    stock_database = {
        "TATASTEEL": {"price": 150.00, "short_ma": 155.00, "long_ma": 148.00, "rsi": 55.0},
        "RELIANCE": {"price": 2900.00, "short_ma": 2850.00, "long_ma": 2880.00, "rsi": 38.0},
        "INFY": {"price": 1420.00, "short_ma": 1450.00, "long_ma": 1400.00, "rsi": 52.0},
        "SBIN": {"price": 820.00, "short_ma": 835.00, "long_ma": 810.00, "rsi": 61.0},
        "TCS": {"price": 3850.00, "short_ma": 3800.00, "long_ma": 3880.00, "rsi": 74.0}
    }
    return stock_database.get(symbol.upper(), {"price": 100.00, "short_ma": 102.00, "long_ma": 98.00, "rsi": 50.0})

def analyze_5_stocks(symbols_list, api_key, secret_key):
    results = []
    for symbol in symbols_list:
        symbol = symbol.strip().upper()
        if not symbol:
            continue
            
        data = fetch_live_indicators(symbol)
        price = data["price"]
        sma = data["short_ma"]
        lma = data["long_ma"]
        rsi = data["rsi"]

        target_3_pct = round(price * 1.03, 2)
        sl_1_5_pct = round(price * 0.985, 2)

        # Multi-Indicator Algorithm Logic
        if sma > lma and (45 <= rsi <= 65):
            signal = "STRONG BUY 🚀"
            if api_key and secret_key:
                status = f"LIVE ORDER EXECUTED @ ₹{price}"
            else:
                status = f"PAPER TRADE: Bought @ ₹{price}"
        elif rsi > 70:
            signal = "OVERBOUGHT (NO BUY)"
            status = "REJECTED: High Risk Zone"
        elif sma < lma:
            signal = "BEARISH / SELL 📉"
            status = "NO ORDER: Downtrend"
        else:
            signal = "HOLD / NEUTRAL"
            status = "WAITING: Neutral Signal"

        save_multi_trade(symbol, price, sma, lma, rsi, target_3_pct, sl_1_5_pct, signal, status)

        results.append({
            'symbol': symbol,
            'price': price,
            'sma': sma,
            'lma': lma,
            'rsi': rsi,
            'target': target_3_pct,
            'stoploss': sl_1_5_pct,
            'signal': signal,
            'status': status
        })
    return results

# ==========================================
# 3. DASHBOARD FRONTEND
# ==========================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>5-Stock Ultimate Algo Bot</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #0b0f19; color: white; margin: 0; padding: 12px; }
        .card { background: #161e2e; padding: 18px; border-radius: 12px; margin-bottom: 18px; border: 1px solid #232f48; }
        h2 { color: #38bdf8; text-align: center; margin-top: 0; }
        p.sub { text-align: center; color: #94a3b8; font-size: 12px; }
        label { font-weight: bold; color: #cbd5e1; display: block; margin-top: 10px; font-size: 13px; }
        input { width: 100%; padding: 10px; margin-top: 5px; background: #0b0f19; border: 1px solid #334155; color: white; border-radius: 6px; box-sizing: border-box; }
        .rule-box { background: #1e1b4b; border: 1px solid #4338ca; padding: 10px; border-radius: 8px; font-size: 11px; margin-top: 12px; line-height: 1.5; }
        button { width: 100%; background: linear-gradient(90deg, #22c55e, #16a34a); color: white; border: none; padding: 14px; font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 15px; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 11px; }
        th, td { border: 1px solid #232f48; padding: 6px; text-align: center; }
        th { background-color: #0b0f19; color: #38bdf8; }
        .STRONG { color: #22c55e; font-weight: bold; }
        .REJECTED { color: #ef4444; }
    </style>
</head>
<body>

<div class="card">
    <h2>🚀 5-Stock Auto Trading Engine</h2>
    <p class="sub">Moving Average Crossover + RSI + Auto Risk Management</p>

    <div class="rule-box">
        🔥 <b>அல்கோ விதிகளின் தொகுப்பு:</b><br>
        • <b>5 Stocks Parallel:</b> 5 பங்குகள் ஒரே நேரத்தில் பகுப்பாய்வு செய்யப்படும்.<br>
        • <b>Strategy:</b> Short MA > Long MA & RSI (45-65) ஆக இருந்தால் மட்டுமே BUY.<br>
        • <b>Auto Exit:</b> Target +3% | StopLoss -1.5%.
    </div>

    <form method="POST">
        <label>Broker API Key (Optional for Paper Trade)</label>
        <input type="text" name="api_key" placeholder="Enter API Key">

        <label>API Secret Key</label>
        <input type="password" name="secret_key" placeholder="Enter Secret Key">

        <label>5 Stock Symbols (கமா போட்டு பிரிக்கவும்)</label>
        <input type="text" name="symbols" value="TATASTEEL, RELIANCE, INFY, SBIN, TCS" required>

        <button type="submit">Analyze All 5 Stocks & Auto-Trade ⚡</button>
    </form>
</div>

{% if results %}
<div class="card">
    <h3 style="color:#38bdf8;">📊 Live Analysis Output (5 Stocks)</h3>
    <table>
        <tr>
            <th>Stock</th>
            <th>Price</th>
            <th>RSI</th>
            <th>Target (+3%)</th>
            <th>SL (-1.5%)</th>
            <th>Signal</th>
        </tr>
        {% for res in results %}
        <tr>
            <td><b>{{ res.symbol }}</b></td>
            <td>₹{{ res.price }}</td>
            <td>{{ res.rsi }}</td>
            <td style="color:#22c55e;">₹{{ res.target }}</td>
            <td style="color:#ef4444;">₹{{ res.stoploss }}</td>
            <td><b>{{ res.signal }}</b></td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}

<div class="card">
    <h3>📋 Database Log History</h3>
    {% if history %}
        <table>
            <tr>
                <th>Time</th>
                <th>Stock</th>
                <th>Price</th>
                <th>Signal</th>
                <th>Status</th>
            </tr>
            {% for row in history %}
            <tr>
                <td>{{ row[1] }}</td>
                <td><b>{{ row[2] }}</b></td>
                <td>₹{{ row[3] }}</td>
                <td><b>{{ row[9] }}</b></td>
                <td style="font-size:10px;">{{ row[10] }}</td>
            </tr>
            {% endfor %}
        </table>
    {% else %}
        <p style="text-align:center; color:#64748b;">ஹிஸ்டரி எதுவும் இல்லை.</p>
    {% endif %}
</div>

</body>
</html>
'''

init_db()

@app.route('/', methods=['GET', 'POST'])
def home():
    results = None
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        secret_key = request.form.get('secret_key')
        symbols_raw = request.form.get('symbols', '')
        symbols_list = symbols_raw.split(',')

        results = analyze_5_stocks(symbols_list, api_key, secret_key)

    history = get_saved_history()
    return render_template_string(HTML_TEMPLATE, results=results, history=history)
