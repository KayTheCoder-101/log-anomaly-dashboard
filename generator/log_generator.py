import random
import time
import requests
from datetime import datetime, timezone
from faker import Faker

fake = Faker()

API_URL = "http://localhost:8000/logs"

ENDPOINTS = ["/login", "/logout", "/home", "/api/users", "/api/orders", "/checkout", "/search", "/profile"]
METHODS = ["GET", "POST", "PUT", "DELETE"]
NORMAL_STATUS_CODES = [200, 200, 200, 201, 204, 301, 404]
ERROR_STATUS_CODES = [500, 502, 503]


def send_log(log):
    try:
        response = requests.post(API_URL, json=log)
        if response.status_code == 200:
            print(f"Sent: {log['endpoint']} [{log['status_code']}] from {log['source_ip']}")
        else:
            print(f"Failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"Error sending log: {e}")


def generate_normal_log():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_ip": fake.ipv4(),
        "endpoint": random.choice(ENDPOINTS),
        "method": random.choice(METHODS),
        "status_code": random.choice(NORMAL_STATUS_CODES),
        "response_time_ms": round(max(5, random.gauss(120, 30)), 2),
        "bytes_sent": random.randint(200, 5000),
        "user_agent": fake.user_agent(),
    }


def generate_anomaly_log(anomaly_type, fixed_ip=None):
    log = generate_normal_log()
    if anomaly_type == "slow_response":
        log["response_time_ms"] = round(random.uniform(2000, 8000), 2)
    elif anomaly_type == "server_error":
        log["status_code"] = random.choice(ERROR_STATUS_CODES)
    elif anomaly_type == "ip_hammering":
        log["source_ip"] = fixed_ip
        log["endpoint"] = "/login"
    return log


def traffic_spike_burst(n=20):
    print(f"--- Injecting traffic spike burst ({n} logs) ---")
    for _ in range(n):
        send_log(generate_normal_log())
        time.sleep(0.05)


def repeated_errors_burst(n=8):
    print(f"--- Injecting repeated server errors ({n} logs) ---")
    for _ in range(n):
        send_log(generate_anomaly_log("server_error"))
        time.sleep(0.1)


def ip_hammering_burst(n=15):
    ip = fake.ipv4()
    print(f"--- Injecting IP hammering burst from {ip} ({n} logs) ---")
    for _ in range(n):
        send_log(generate_anomaly_log("ip_hammering", fixed_ip=ip))
        time.sleep(0.05)


def main():
    print("Log generator started. Press Ctrl+C to stop.")
    count = 0
    while True:
        send_log(generate_normal_log())
        count += 1
        if count % 30 == 0:
            anomaly = random.choice([traffic_spike_burst, repeated_errors_burst, ip_hammering_burst])
            anomaly()
        time.sleep(0.5)


if __name__ == "__main__":
    main()