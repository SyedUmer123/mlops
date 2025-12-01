# test_app.py
from app import app, todos
import pytest
from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_todos():
    todos.clear()

def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "Todo App v1" in response.text

def test_create_todo():
    response = client.post("/todos", json={"title": "Test Todo", "done": False})
    assert response.status_code == 200
    assert response.json()["title"] == "Test Todo"
    assert response.json()["done"] == False

def test_list_todos():
    client.post("/todos", json={"title": "Test Todo 1", "done": False})
    client.post("/todos", json={"title": "Test Todo 2", "done": False})
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_update_todo():
    response = client.post("/todos", json={"title": "Test Todo", "done": False})
    todo_id = response.json()["id"]
    response = client.put(f"/todos/{todo_id}", json={"title": "Updated Test Todo"})
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Test Todo"

def test_delete_todo():
    response = client.post("/todos", json={"title": "Test Todo", "done": False})
    todo_id = response.json()["id"]
    response = client.delete(f"/todos/{todo_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_update_non_existent_todo():
    response = client.put("/todos/1", json={"title": "Updated Test Todo"})
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"

def test_delete_non_existent_todo():
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"