import requests

API_KEY = "YOUR_KEY_HERE"

url = "https://api.deepseek.com/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "user", "content": "Hello"}
    ]
}

res = requests.post(url, headers=headers, json=payload)

print(res.status_code)
print(res.text)
