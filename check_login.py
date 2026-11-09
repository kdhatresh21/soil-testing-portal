import app

client = app.app.test_client()
response = client.get("/login")

print("STATUS:", response.status_code)
print("TOKEN PRESENT:", b"csrf_token" in response.data)