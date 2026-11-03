import asyncio
from backend.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print("GET /")
response = client.get("/")
print(response.status_code)
print(response.content[:100])

print("\nGET /api/")
response = client.get("/api/")
print(response.status_code)
print(response.content)

print("\nGET /drugs.html")
response = client.get("/drugs.html")
print(response.status_code)
print(response.content[:100])
