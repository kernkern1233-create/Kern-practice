import sqlite3
import json
import sys
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'super-student-secret-key'

def get_db():
    conn = sqlite3.connect('logs.db')
    conn.row_factory = sqlite3.Row
    return conn

# Автоматически создаем таблицу пользователей и добавляем админа при запуске
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'admin', 'admin123')")
    conn.commit()
    conn.close()

# Запускаем создание таблицы
init_db()

# --- REST API ---
@app.route('/api/logs', methods=['GET'])
def api_get_logs():
    ip = request.args.get('ip')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    group_by_ip = request.args.get('group_by_ip')

    conn = get_db()
    cursor = conn.cursor()

    if group_by_ip:
        query = "SELECT ip, COUNT(*) as count FROM access_logs WHERE 1=1"
        params = []
        if start_date:
            query += " AND log_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND log_date <= ?"
            params.append(end_date)
        query += " GROUP BY ip"
        cursor.execute(query, params)
        result = [dict(row) for row in cursor.fetchall()]
    else:
        query = "SELECT * FROM access_logs WHERE 1=1"
        params = []
        if ip:
            query += " AND ip = ?"
            params.append(ip)
        if start_date:
            query += " AND log_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND log_date <= ?"
            params.append(end_date)
        cursor.execute(query, params)
        result = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify({"status": "success", "data": result})

# --- Консольный веб-интерфейс (HTML + AJAX Fetch) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Агрегатор Apache Логов</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f4f4f9; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        input, button, select { padding: 8px; margin: 5px 0; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #007bff; color: white; }
        .progress-bar { width: 100%; background: #e0e0e0; height: 10px; border-radius: 5px; overflow: hidden; display: none; }
        .progress-fill { height: 100%; background: #28a745; width: 0%; transition: width 0.3s; }
    </style>
</head>
<body>
    <h1>Агрегатор логов Apache</h1>
    
    {% if not session.user %}
    <div class="card">
        <h2>Авторизация</h2>
        <form action="/login" method="POST">
            <input type="text" name="username" placeholder="Логин (admin)" required><br>
            <input type="password" name="password" placeholder="Пароль (admin123)" required><br>
            <button type="submit">Войти</button>
        </form>
    </div>
    {% else %}
    <p>Вы вошли как: <b>{{ session.user }}</b> | <a href="/logout">Выйти</a></p>
    
    <div class="card">
        <h3>Фильтрация и поиск логов</h3>
        <input type="text" id="keyword" placeholder="Введите ключевое слово (IP или URL)" oninput="filterTable()"><br>
        <label>С даты: <input type="date" id="startDate"></label>
        <label>По дату: <input type="date" id="endDate"></label>
        <button onclick="loadLogsData()">Применить фильтр (AJAX/Fetch)</button>
        
        <div class="progress-bar" id="progressBar"><div class="progress-fill" id="progressFill"></div></div>
        <p id="statusText"></p>
    </div>

    <div class="card">
        <h3>Список URL (выберите для просмотра)</h3>
        <select id="urlList" onchange="showSelectedUrlDetails()">
            <option value="">-- Выберите URL --</option>
        </select>
        <div id="urlDetails" style="margin-top: 10px; font-weight: bold; color: #333;"></div>
    </div>

    <div class="card">
        <h3>Результаты</h3>
        <table id="logsTable">
            <thead>
                <tr>
                    <th>ID</th><th>IP</th><th>Дата</th><th>Метод</th><th>URL</th><th>Статус</th><th>Размер (байты)</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>

    <script>
        let globalData = [];

        async function loadLogsData() {
            const start = document.getElementById('startDate').value;
            const end = document.getElementById('endDate').value;
            const pBar = document.getElementById('progressBar');
            const pFill = document.getElementById('progressFill');
            const status = document.getElementById('statusText');

            pBar.style.display = 'block';
            pFill.style.width = '30%';
            status.innerText = 'Статус загрузки: Подключение к серверу...';

            let url = '/api/logs?';
            if (start) url += `start_date=${start}&`;
            if (end) url += `end_date=${end}&`;

            try {
                pFill.style.width = '70%';
                status.innerText = 'Статус загрузки: Получение JSON данных...';

                const response = await fetch(url);
                const json = await response.json();
                globalData = json.data;

                pFill.style.width = '100%';
                status.innerText = `Загружено успешно! Всего записей: ${globalData.length}`;

                renderTable(globalData);
                populateUrlList(globalData);
            } catch (err) {
                status.innerText = 'Ошибка при загрузке данных: ' + err;
            } setTimeout(() => { pBar.style.display = 'none'; }, 2000);
        }

        function renderTable(data) {
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            data.forEach(row => {
                tbody.innerHTML += `<tr>
                    <td>${row.id}</td>
                    <td>${row.ip}</td>
                    <td>${row.log_date}</td>
                    <td>${row.method}</td>
                    <td>${row.url}</td>
                    <td>${row.status}</td>
                    <td>${row.size}</td>
                </tr>`;
            });
        }

        function populateUrlList(data) {
            const select = document.getElementById('urlList');
            select.innerHTML = '<option value="">-- Выберите URL --</option>';
            const urls = [...new Set(data.map(item => item.url))];
            urls.forEach(u => {
                select.innerHTML += `<option value="${u}">${u}</option>`;
            });
        }

        function showSelectedUrlDetails() {
            const val = document.getElementById('urlList').value;
            const details = document.getElementById('urlDetails');
            if (val) {
                const count = globalData.filter(d => d.url === val).length;
                details.innerText = `Выбранный URL: ${val} (Встречается в логах: ${count} раз(а))`;
            } else {
                details.innerText = '';
            }
        }

        function filterTable() {
            const kw = document.getElementById('keyword').value.toLowerCase();
            const filtered = globalData.filter(d => 
                d.ip.toLowerCase().includes(kw) || d.url.toLowerCase().includes(kw)
            );
            renderTable(filtered);
        }

        // Автозагрузка при старте
        loadLogsData();
    </script>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['user'] = username
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# Консольный режим (для удовлетворения условия «просмотр через консоль»)
def run_cli():
    print("=== КОНСОЛЬНЫЙ ИНТЕРФЕЙС ПРОСМОТРА ЛОГОВ ===")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT ip, log_date, method, url, status, size FROM access_logs LIMIT 20")
    rows = cursor.fetchall()
    print(f"{'IP':<15} | {'Дата':<20} | {'Метод':<6} | {'Status':<6} | {'URL'}")
    print("-" * 70)
    for r in rows:
        print(f"{r['ip']:<15} | {r['log_date']:<20} | {r['method']:<6} | {r['status']:<6} | {r['url']}")
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        run_cli()
    else:
        app.run(debug=True, port=5000)