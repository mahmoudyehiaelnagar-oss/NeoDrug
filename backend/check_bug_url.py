from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app
import urllib.parse
client = TestClient(app)

response = client.get(f"/api/drugs/{urllib.parse.quote('A-H')}")
print("A-H:", response.status_code, response.json().get('trade_en'))
response = client.get(f"/api/drugs/{urllib.parse.quote('A-Viton')}")
print("A-Viton:", response.status_code, response.json().get('trade_en'))
response = client.get(f"/api/drugs/{urllib.parse.quote('Abilaxine')}")
print("Abilaxine:", response.status_code, response.json().get('trade_en'))
