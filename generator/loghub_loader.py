import os
import re
import time
from datetime import datetime

from common import send_log

API_URL = os.environ.get("API_URL", "http://localhost:8000/logs")
LOGHUB_FILE_PATH = os.environ.get("LOGHUB_FILE_PATH", "/data/NASA_access_log_Jul95")
SEND_DELAY = float(os.environ.get("LOGHUB_SEND_DELAY", "0"))
MAX_LINES = int(os.environ.get("LOGHUB_MAX_LINES", "0"))

LOG_PATTERN = re.compile(
    r'(?P<host>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<endpoint>\S+)(?: \S+)?" '
    r'(?P<status>\d+) (?P<bytes>\S+)'
)


def parse_line(line):
    match = LOG_PATTERN.match(line)
    if not match:
        return None

    parts = match.groupdict()

    try:
        ts = datetime.strptime(parts["timestamp"], "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None

    raw_bytes = parts["bytes"]
    bytes_sent = 0 if raw_bytes == "-" else int(raw_bytes)

    return {
        "timestamp": ts.isoformat(),
        "source_ip": parts["host"],
        "endpoint": parts["endpoint"],
        "method": parts["method"],
        "status_code": int(parts["status"]),
        "response_time_ms": None,
        "bytes_sent": bytes_sent,
        "user_agent": None,
    }


def main():
    print(f"Loading LogHub file: {LOGHUB_FILE_PATH}")
    sent, failed, skipped = 0, 0, 0

    with open(LOGHUB_FILE_PATH, "r", encoding="latin-1") as f:
        for i, line in enumerate(f):
            if MAX_LINES and i >= MAX_LINES:
                break

            log = parse_line(line)
            if log is None:
                skipped += 1
                continue

            result = send_log(log, API_URL)
            if result is not None:
                sent += 1
            else:
                failed += 1

            if SEND_DELAY:
                time.sleep(SEND_DELAY)

    print(f"Done. Sent: {sent}, Failed: {failed}, Skipped (unparsed): {skipped}")


if __name__ == "__main__":
    main()
