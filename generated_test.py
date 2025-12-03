import pytest
from fastapi.testclient import TestClient
from app import app, todos

client = TestClient(app)

def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "Todo App v1" in response.text

def test_create_todo():
    response = client.post("/todos", json={"title": "Test Todo"})
    assert response.status_code == 200
    assert "id" in response.json()
    assert "title" in response.json()
    assert "done" in response.json()

def test_list_todos():
    client.post("/todos", json={"title": "Test Todo 1"})
    client.post("/todos", json={"title": "Test Todo 2"})
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_update_todo():
    client.post("/todos", json={"title": "Test Todo"})
    response = client.put("/todos/1", json={"title": "Updated Todo"})
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Todo"

def test_delete_todo():
    client.post("/todos", json={"title": "Test Todo"})
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_not_found_todo():
    response = client.get("/todos/1")
    assert response.status_code == 404

def test_create_todo_invalid_json():
    response = client.post("/todos", json={"invalid": "json"})
    assert response.status_code == 422

def test_update_todo_invalid_json():
    client.post("/todos", json={"title": "Test Todo"})
    response = client.put("/todos/1", json={"invalid": "json"})
    assert response.status_code == 422

def test_delete_todo_invalid_id():
    response = client.delete("/todos/abc")
    assert response.status_code == 422

def test_list_todos_empty():
    todos.clear()
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_update_todo_not_found():
    response = client.put("/todos/1", json={"title": "Updated Todo"})
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"

def test_delete_todo_not_found():
    response = client.delete("/todos/1")
    assert response.status_code == 200
    assert response.json()["status"] == "not_found"