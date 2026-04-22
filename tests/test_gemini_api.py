"""
Test Gemini API key is working
"""

import requests
import os
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("GOOGLE_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

response = requests.get(url)

if response.status_code == 200:
    print("✅ API key is working!")
    print(response.json())
else:
    print("❌ API key failed!")
    print("Status Code:", response.status_code)
    print("Response:", response.text)