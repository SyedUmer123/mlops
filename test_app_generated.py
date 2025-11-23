import pytest
from fastapi.testclient import TestClient
from app import app, todos

@pytest.fixture(autouse=True)
def clear_todos():
    todos.clear()

client = TestClient(app)

def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "Todo App v1" in response.text

def test_create_todo():
    response = client.post("/todos", json={"title": "New Todo", "done": False})
    assert response.status_code == 200
    assert response.json()["title"] == "New Todo"
    assert response.json()["done"] == False

def test_create_todo_empty_title():
    response = client.post("/todos", json={"title": "", "done": False})
    assert response.status_code == 200
    assert response.json()["title"] == ""
    assert response.json()["done"] == False

def test_list_todos():
    client.post("/todos", json={"title": "New Todo", "done": False})
    client.post("/todos", json={"title": "Another Todo", "done": True})
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_delete_todo():
    client.post("/todos", json={"title": "New Todo", "done": False})
    response = client.get("/todos")
    todo_id = response.json()[0]["id"]
    response = client.delete(f"/todos/{todo_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_delete_non_existent_todo():
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"