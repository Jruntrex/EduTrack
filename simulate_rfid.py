import requests
import json
import time
import sys

# Налаштування
SERVER_URL = "http://127.0.0.1:8000/api/card-scan/"

def print_status(message, color="white"):
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "white": "\033[0m",
        "blue": "\033[94m"
    }
    print(f"{colors.get(color, colors['white'])}{message}{colors['white']}")

def simulate_scan():
    print("-------------------------------------------------")
    print_status("🤖 ВІРТУАЛЬНИЙ ТУРНІКЕТ ЗАПУЩЕНО", "blue")
    print("Введіть UID картки (наприклад: A1B2C3D4) і натисніть Enter.")
    print("Щоб вийти, натисніть Ctrl+C")
    print("-------------------------------------------------")

    while True:
        try:
            uid = input("\n💳 Пікнути карткою (введіть UID): ").strip()
            
            if not uid:
                continue

            print_status(f"📡 Відправляю сигнал на сервер... [UID: {uid}]", "yellow")

            try:
                # Імітуємо роботу ESP32 (HTTP POST)
                response = requests.post(
                    SERVER_URL, 
                    json={"uid": uid}, 
                    timeout=2
                )
                
                data = response.json()
                
                # Імітуємо реакцію світлодіодів
                if response.status_code == 200 and data.get('status') == 'success':
                    print_status("🟢 [ПІК!] ВХІД/ВИХІД ДОЗВОЛЕНО", "green")
                    print(f"   Повідомлення: {data.get('message')}")
                else:
                    print_status("🔴 [ПІК-ПІК-ПІК] ПОМИЛКА", "red")
                    print(f"   Повідомлення: {data.get('message')}")

            except requests.exceptions.ConnectionError:
                print_status("🔥 ПОМИЛКА: Сервер не відповідає. Ти запустив Django?", "red")
            except Exception as e:
                print_status(f"🔥 ПОМИЛКА: {e}", "red")

        except KeyboardInterrupt:
            print("\n👋 Вимикаю турнікет...")
            break

if __name__ == "__main__":
    simulate_scan()