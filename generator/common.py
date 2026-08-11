import requests

def send_log(log, api_url):
    """POST a single log dict to the ingestion API.
    Returns the parsed JSON response dict on success (includes 'id'), or None on failure."""
    try:
        response = requests.post(api_url, json=log)
        if response.status_code == 200:
            data = response.json()
            print(f"Sent: {log['endpoint']} [{log['status_code']}] from {log['source_ip']} (id={data['id']})")
            return data
        else:
            print(f"Failed ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"Error sending log: {e}")
        return None
