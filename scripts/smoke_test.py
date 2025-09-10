import json
from fastapi.testclient import TestClient

# Import the FastAPI app instance
from backend.app import app

def main():
    with TestClient(app) as client:
        r = client.get("/api/health")
        print("/api/health:")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))

        r2 = client.post("/api/chat", json={"message": "Hi"})
        print("/api/chat (Hi):")
        print(json.dumps(r2.json(), indent=2, ensure_ascii=False))

        r3 = client.post("/api/chat", json={"message": "Is there parking?", "lang": "en"})
        print("/api/chat (parking):")
        print(json.dumps(r3.json(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

