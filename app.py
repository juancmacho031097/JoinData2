import requests
import os

headers = {
    "Authorization": "Bearer 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",
    "HTTP-Referer": "https://ustariz-pizza-bot.onrender.com",
    "X-Title": "Bot Ustariz Pizza",
    "Content-Type": "application/json"
}

data = {
    "model": "google/gemma-3-4b-it:free",  # Cambia a otro modelo si falla
    "messages": [{"role": "user", "content": "Hola"}]
}

r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
print(r.status_code)
print(r.text)