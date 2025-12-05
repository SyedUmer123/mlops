from fastapi.testclient import TestClient
from app import app, todos
from pydantic import BaseModel
import pytest

@pytest.fixture(autouse=True)
def clear_todos():
    todos.clear()

client = TestClient(app)

def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "Todo App v1" in response.text

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "v1.1"}

def test_create_todo():
    payload = {"title": "Test Todo", "done": False}
    response = client.post("/todos", json=payload)
    assert response.status_code == 200
    assert "id" in response.json()
    assert "title" in response.json()
    assert "done" in response.json()

def test_list_todos():
    payload = {"title": "Test Todo", "done": False}
    client.post("/todos", json=payload)
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_update_todo():
    payload = {"title": "Test Todo", "done": False}
    response = client.post("/todos", json=payload)
    todo_id = response.json()["id"]
    update_payload = {"title": "Updated Todo"}
    response = client.put(f"/todos/{todo_id}", json=update_payload)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Todo"

def test_delete_todo():
    payload = {"title": "Test Todo", "done": False}
    response = client.post("/todos", json=payload)
    todo_id = response.json()["id"]
    response = client.delete(f"/todos/{todo_id}")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_update_todo_partial():
    payload = {"title": "Test Todo", "done": False}
    response = client.post("/todos", json=payload)
    todo_id = response.json()["id"]
    class TodoUpdate(BaseModel):
        title: str = None
        done: bool = None
    update_payload = TodoUpdate(title="Updated Todo")
    response = client.put(f"/todos/{todo_id}", json=update_payload.model_dump(exclude_unset=True))
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Todo"

def test_update_todo_not_found():
    update_payload = {"title": "Updated Todo"}
    response = client.put("/todos/999", json=update_payload)
    assert response.status_code == 200
    assert response.json() == {"status": "not_found"}

def test_delete_todo_not_found():
    response = client.delete("/todos/999")
    assert response.status_code == 200
    assert response.json() == {"status": "not_found"}