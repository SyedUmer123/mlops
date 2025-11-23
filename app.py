# v1/app.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Todo Demo v1")

# In-memory store (simple)
todos = {}
next_id = 1

class TodoCreate(BaseModel):
    title: str
    done: bool = False

@app.get("/", response_class=HTMLResponse)
def home():
    html = """
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>Todo v1</title></head>
      <body>
        <h1>Todo App v1</h1>
        <input id="todoTitle" placeholder="New todo"/>
        <button id="addBtn">Add</button>
        <ul id="todoList"></ul>
        <script>
          async function refresh() {
            const res = await fetch('/todos');
            const data = await res.json();
            const list = document.getElementById('todoList');
            list.innerHTML = '';
            data.forEach(t => {
              const li = document.createElement('li');
              li.id = 'todo-' + t.id;
              li.innerHTML = `<span class="title">${t.title}</span>
                              <button class="delBtn" data-id="${t.id}">Delete</button>`;
              list.appendChild(li);
            });
            document.querySelectorAll('.delBtn').forEach(b => {
              b.onclick = async () => {
                await fetch('/todos/' + b.dataset.id, {method:'DELETE'});
                refresh();
              };
            });
          }
          document.getElementById('addBtn').onclick = async () => {
            const title = document.getElementById('todoTitle').value;
            await fetch('/todos', {
              method:'POST',
              headers:{'Content-Type':'application/json'},
              body: JSON.stringify({title})
            });
            document.getElementById('todoTitle').value = '';
            refresh();
          };
          refresh();
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/todos")
def create_todo(payload: TodoCreate):
    global next_id
    tid = next_id
    todos[tid] = {"id": tid, "title": payload.title, "done": payload.done}
    next_id += 1
    return todos[tid]

@app.get("/todos")
def list_todos():
    return list(todos.values())

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    if todo_id in todos:
        todos.pop(todo_id)
        return {"status": "ok"}
    return {"status": "not_found"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
