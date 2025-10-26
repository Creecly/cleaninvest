# test_load.py
import requests
import threading
import time

def test_user():
    session = requests.Session()
    # Регистрация
    response = session.post('https://your-app.railway.app/register', json={
        'name': f'Test User {time.time()}',
        'nickname': f'testuser{time.time()}',
        'email': f'test{time.time()}@example.com',
        'password': 'testpassword123'
    })
    print(f"Registration: {response.status_code}")

# Запуск 100 потоков для теста
threads = []
for i in range(100):
    t = threading.Thread(target=test_user)
    threads.append(t)
    t.start()

for t in threads:
    t.join()