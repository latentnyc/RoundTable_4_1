import json
import sys

def parse_logs(file_path):
    try:
        content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='utf-16') as f:
                content = f.read()

        logs = json.loads(content)

        # Filter for stdout/stderr logs with textPayload
        extracted_logs = []
        for entry in logs:
            if 'textPayload' in entry:
                timestamp = entry.get('timestamp', 'UNKNOWN')
                text = entry['textPayload']
                extracted_logs.append(f"{timestamp} - {text}")

        # Sort by timestamp
        extracted_logs.sort()

        print(f"Found {len(extracted_logs)} log entries:")
        for log in extracted_logs:
            print(log.strip())

    except Exception as e:
        print(f"Error parsing logs: {e}")

if __name__ == "__main__":
    file_path = "trace_logs.json"
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    parse_logs(file_path)
