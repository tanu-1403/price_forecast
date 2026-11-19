
import requests

url = "https://api.agmarknet.gov.in/v1/daily-price-arrival/filters"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

response = requests.get(
    url,
    headers=headers,
    timeout=30
)

print("Status code:", response.status_code)

response.raise_for_status()

data = response.json()

print("\nResponse type:", type(data))
print("\nAvailable keys:", data.keys() if isinstance(data, dict) else "Not a dictionary")

print("\nFull response:")
print(data)

print("\nMAHARASHTRA:")
for item in data.get("state_data", []):
    if "maharashtra" in str(item).lower():
        print(item)

print("\nWHEAT AND MAIZE:")
for item in data.get("cmdt_data", []):
    name = str(item).lower()
    if "wheat" in name or "maize" in name:
        print(item)
