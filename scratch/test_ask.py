import requests

url = "http://localhost:8001/api/ask"
# Try without headers
try:
    r = requests.post(url, json={})
    print("Without headers:", r.status_code, r.json())
except Exception as e:
    print("Without headers error:", e)

# Try with authorization header
# Let's register/login a user first
url_reg = "http://localhost:8001/api/auth/register"
url_login = "http://localhost:8001/api/auth/login"
email = "admin@up.gov"
password = "admin123"

try:
    r_login = requests.post(url_login, json={"email": email, "password": password})
    token = r_login.json()["data"]["access_token"]
    print("Logged in successfully, token exists:", bool(token))
    
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(url, json={"question": "summarize this data", "source_id": "csv_latest"}, headers=headers)
    print("With headers:", r.status_code, r.json())
except Exception as e:
    print("Login/ask error:", e)
