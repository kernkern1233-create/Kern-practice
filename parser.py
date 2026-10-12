import os
import glob
import sqlite3

# Создаем папку и файл, если их нет
if not os.path.exists('logs'):
    os.makedirs('logs')

test_log_path = os.path.join('logs', 'access.log')
if not os.path.exists(test_log_path):
    with open(test_log_path, 'w', encoding='utf-8') as f:
        f.write('192.168.1.1 - - [10/Oct/2026:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 2326\n')
        f.write('10.0.0.5 - - [10/Oct/2026:14:00:12 +0000] "POST /login HTTP/1.1" 404 512\n')

def parse_logs():
    log_files = glob.glob(os.path.join('logs', '*.log'))
    conn = sqlite3.connect('logs.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            log_date TEXT NOT NULL,
            method TEXT,
            url TEXT,
            status INTEGER,
            size INTEGER
        )
    """)
    
    count = 0
    for file_path in log_files:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) > 8:
                    ip = parts[0]
                    log_date = parts[3].replace('[', '')
                    method = parts[5].replace('"', '')
                    url = parts[6]
                    status = int(parts[8]) if parts[8].isdigit() else 200
                    size = int(parts[9]) if len(parts) > 9 and parts[9].isdigit() else 0
                    
                    cursor.execute("""
                        INSERT INTO access_logs (ip, log_date, method, url, status, size)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (ip, log_date, method, url, status, size))
                    count += 1

    conn.commit()
    conn.close()
    print(f"Успешно обработано и добавлено записей: {count}")

if __name__ == '__main__':
    parse_logs()