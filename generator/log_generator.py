import random
import time
from datetime import datetime, timezone
from faker import Faker
from common import send_log
import os

fake = Faker()
API_URL = os.getenv("API_URL", "http://localhost:8000/logs")

ENDPOINTS = ["/login", "/logout", "/home", "/api/users", "/api/orders", "/checkout", "/search", "/profile"]
METHODS = ["GET", "POST", "PUT", "DELETE"]
NORMAL_STATUS_CODES = [200, 200, 200, 201, 204, 301, 404]
ERROR_STATUS_CODES = [500, 502, 503]


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
        result = send_log(generate_normal_log(), API_URL)
        time.sleep(0.05)


def repeated_errors_burst(n=8):
    print(f"--- Injecting repeated server errors ({n} logs) ---")
    for _ in range(n):
        result = send_log(generate_anomaly_log("server_error"), API_URL)
        time.sleep(0.1)


def ip_hammering_burst(n=15):
    ip = fake.ipv4()
    print(f"--- Injecting IP hammering burst from {ip} ({n} logs) ---")
    for _ in range(n):
        result = send_log(generate_anomaly_log("ip_hammering", fixed_ip=ip), API_URL)
        time.sleep(0.05)


def main():
    print("Log generator started. Press Ctrl+C to stop.")
    count = 0
    while True:
        send_log(generate_normal_log(), API_URL)
        count += 1
        if count % 30 == 0:
            anomaly = random.choice([traffic_spike_burst, repeated_errors_burst, ip_hammering_burst])
            anomaly()
        time.sleep(0.5)


if __name__ == "__main__":
    main()