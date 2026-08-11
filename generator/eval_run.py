import json
import os
import time

from common import send_log
from log_generator import generate_normal_log, generate_anomaly_log, fake

API_URL = os.environ.get("API_URL", "http://localhost:8000/logs")
GROUND_TRUTH_PATH = os.environ.get("GROUND_TRUTH_PATH", "/data/ground_truth.jsonl")

N_NORMAL = int(os.environ.get("EVAL_N_NORMAL", "200"))
N_ERROR_BURSTS = int(os.environ.get("EVAL_N_ERROR_BURSTS", "3"))
N_HAMMER_BURSTS = int(os.environ.get("EVAL_N_HAMMER_BURSTS", "3"))


def record(f, log_id, true_label, anomaly_type):
    f.write(json.dumps({
        "id": log_id,
        "true_label": true_label,  # 0 = normal, 1 = anomaly
        "anomaly_type": anomaly_type,
    }) + "\n")


def main():
    os.makedirs(os.path.dirname(GROUND_TRUTH_PATH), exist_ok=True)

    with open(GROUND_TRUTH_PATH, "w") as f:
        print(f"--- Sending {N_NORMAL} normal logs ---")
        for _ in range(N_NORMAL):
            result = send_log(generate_normal_log(), API_URL)
            if result:
                record(f, result["id"], 0, "normal")
            time.sleep(0.02)

        print(f"--- Sending {N_ERROR_BURSTS} repeated-error bursts ---")
        for _ in range(N_ERROR_BURSTS):
            for _ in range(8):
                result = send_log(generate_anomaly_log("server_error"), API_URL)
                if result:
                    record(f, result["id"], 1, "server_error")
                time.sleep(0.05)

        print(f"--- Sending {N_HAMMER_BURSTS} IP-hammering bursts ---")
        for _ in range(N_HAMMER_BURSTS):
            ip = fake.ipv4()
            for _ in range(15):
                result = send_log(generate_anomaly_log("ip_hammering", fixed_ip=ip), API_URL)
                if result:
                    record(f, result["id"], 1, "ip_hammering")
                time.sleep(0.03)

    print(f"Ground truth written to {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    main()
