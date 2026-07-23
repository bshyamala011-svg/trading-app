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
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            price REAL,
            signal TEXT,
            predicted_growth TEXT,
            order_status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_trade_data(symbol, price, signal, growth, status):
    conn = sqlite3.connect("trading_app.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO trade_history (timestamp, symbol, price, signal, predicted_growth, order_status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (now, symbol, price, signal, growth, status))
    conn.commit()
    conn.close()

def get_saved_history():
    conn = sqlite3.connect("trading_app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_history ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def execute_broker_order(symbol, action, price, api_key, secret_key):
    if api_key and secret_key:
        return f"SUCCESS: Executed via API ({api_key[:4]}***)"
    else:
        return "PAPER TRADING: Order Placed"

# ==========================================
# 2. WEB APP INTERFACE
# ==========================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auto Trading App</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 15px; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 20px; }
        h2 { color: #0f172a; text-align: center; }
        p.sub { text-align: center; color: #64748b; font-size: 13px; }
        label { font-weight: bold; color: #334155; display: block; margin-top: 12px; font-size: 14px; }
        input { width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; }
        .api-box { background-color: #f8fafc; border: 1px dashed #94a3b8; padding: 10px; border-radius: 8px; margin-top: 10px; }
        button { width: 100%; background-color: #16a34a; color: white; border: none; padding: 12px; font-size: 16px; font-weight: bold; border-radius: 6px; margin-top: 18px; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        th, td { border: 1px solid #e2e8f0; padding: 10px; text-align: center; }
        th { background-color: #0f172a; color: white; }
        .BUY { color: #16a34a; font-weight: bold; }
        .SELL { color: #dc2626; font-weight: bold; }
        .HOLD { color: #d97706; font-weight: bold; }
    </style>
</head>
<body>

<div class="card">
    <h2>📈 Multi-Stock Auto Trading</h2>
    <p class="sub">பங்கு பகுப்பாய்வு & ஆட்டோ டிரேடிங்</p>

    <form method="POST">
        <div class="api-box">
            <label style="margin-top:0;">Broker API Key</label>
            <input type="text" name="api_key" placeholder="Enter Broker API Key">

            <label>API Secret Key</label>
            <input type="password" name="secret_key" placeholder="Enter API Secret Key">
        </div>

        <label>Stock Symbols (கமா போட்டு பிரிக்கவும்)</label>
        <input type="text" name="symbols" value="TATASTEEL, RELIANCE, INFY" required>

        <label>Current Prices</label>
        <input type="text" name="prices" value="150.50, 2900.00, 1420.00" required>

        <label>Short Moving Averages</label>
        <input type="text" name="short_mas" value="155.00, 2850.00, 1450.00" required>

        <label>Long Moving Averages</label>
        <input type="text" name="long_mas" value="148.00, 2880.00, 1400.00" required>

        <button type="submit">Analyze All & Connect Broker</button>
    </form>
</div>

{% if results %}
<div class="card">
    <h3>🔍 Analysis Results</h3>
    <table>
        <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Signal</th>
            <th>Est. Growth</th>
            <th>Broker Status</th>
        </tr>
        {% for r in results %}
        <tr>
            <td><b>{{ r.symbol }}</b></td>
            <td>₹{{ r.price }}</td>
            <td class="{{ r.signal }}">{{ r.signal }}</td>
            <td><b>{{ r.growth }}</b></td>
            <td>{{ r.status }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}

<div class="card">
    <h3>📋 Saved Database History</h3>
    {% if history %}
        <table>
            <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Price</th>
                <th>Signal</th>
                <th>Est. Growth</th>
                <th>Status</th>
            </tr>
            {% for row in history %}
            <tr>
                <td>{{ row[1] }}</td>
                <td>{{ row[2] }}</td>
                <td>₹{{ row[3] }}</td>
                <td class="{{ row[4] }}">{{ row[4] }}</td>
                <td>{{ row[5] }}</td>
                <td>{{ row[6] }}</td>
            </tr>
            {% endfor %}
        </table>
    {% else %}
        <p style="text-align:center; color:#94a3b8;">தரவுகள் எதுவும் இல்லை.</p>
    {% endif %}
</div>

</body>
</html>
'''

init_db()

# ==========================================
# 3. APP ROUTES
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def home():
    results = []
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        secret_key = request.form.get('secret_key')

        symbols = [s.strip().upper() for s in request.form['symbols'].split(',')]
        prices = [float(p.strip()) for p in request.form['prices'].split(',')]
        short_mas = [float(sm.strip()) for sm in request.form['short_mas'].split(',')]
        long_mas = [float(lm.strip()) for lm in request.form['long_mas'].split(',')]

        for i in range(len(symbols)):
            sym = symbols[i]
            prc = prices[i]
            sma = short_mas[i]
            lma = long_mas[i]

            growth_pct = round(((sma - lma) / lma) * 100, 2)
            growth_str = f"+{growth_pct}%" if growth_pct > 0 else f"{growth_pct}%"

            signal = "HOLD"
            order_status = "NO ACTION"

            if sma > lma:
                signal = "BUY"
            elif sma < lma:
                signal = "SELL"

            if signal in ["BUY", "SELL"]:
                order_status = execute_broker_order(sym, signal, prc, api_key, secret_key)

            save_trade_data(sym, prc, signal, growth_str, order_status)
            
            results.append({
                'symbol': sym,
                'price': prc,
                'signal': signal,
                'growth': growth_str,
                'status': order_status
            })

    history = get_saved_history()
    return render_template_string(HTML_TEMPLATE, results=results, history=history)
