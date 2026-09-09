from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

app = FastAPI(title="FastApi Todos")


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class Todo(BaseModel):
    id: int
    title: str
    completed: bool = False


todos: list[Todo] = []
next_todo_id = 1


def _get_todo(todo_id: int) -> Todo:
    for todo in todos:
        if todo.id == todo_id:
            return todo
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/todos")
def list_todos() -> list[Todo]:
    return todos


@app.post("/todos", status_code=status.HTTP_201_CREATED)
def create_todo(payload: TodoCreate) -> Todo:
    global next_todo_id
    todo = Todo(id=next_todo_id, title=payload.title)
    todos.append(todo)
    next_todo_id += 1
    return todo


@app.patch("/todos/{todo_id}/complete")
def complete_todo(todo_id: int) -> Todo:
    todo = _get_todo(todo_id)
    todo.completed = True
    return todo


@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int) -> Response:
    todo = _get_todo(todo_id)
    todos.remove(todo)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
