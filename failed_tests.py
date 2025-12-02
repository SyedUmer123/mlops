# Failed Test Cases extracted from run
from app import app, todos

def test_create_todo_with_empty_title():
    response = client.post("/todos", json={"title": ""})
    assert response.status_code == 422