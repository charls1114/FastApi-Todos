const BASE = '/todos'

async function request(url, method = 'GET', body) {
  const res = await fetch(url, body
    ? { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
    : { method })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.status === 204 ? null : res.json()
}

export const getTodos = () => request(BASE)
export const createTodo = (todo) => request(BASE, 'POST', todo)
export const updateTodo = (id, todo) => request(`${BASE}/${id}`, 'PUT', todo)
export const deleteTodo = (id) => request(`${BASE}/${id}`, 'DELETE')
