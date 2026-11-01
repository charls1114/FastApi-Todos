const BASE = '/todos'
const TOKEN_KEY = 'todo-token'

let onUnauthorized = () => {}

// 토큰이 만료되거나 잘못되면(401) 로그인 화면으로 돌아가도록 App 이 등록한다
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // 저장소를 쓸 수 없으면 새로고침 시 다시 로그인한다
  }
}

// FastAPI 오류 응답의 detail(문자열 또는 검증 오류 목록)을 읽기 쉬운 문장으로 바꾼다
async function errorMessage(res) {
  const text = await res.text()
  try {
    const { detail } = JSON.parse(text)
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item) => item.msg).join(', ')
  } catch {
    // JSON 이 아니면 원문을 그대로 보여준다
  }
  return `${res.status} ${text}`
}

async function request(url, method = 'GET', body, { form = false } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (body && form) {
    payload = new URLSearchParams(body)
  } else if (body) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(url, { method, headers, body: payload })
  if (res.status === 401 && token) onUnauthorized()
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.status === 204 ? null : res.json()
}

export const register = (user) => request('/auth/register', 'POST', user)
export const login = (username, password) => request('/auth/login', 'POST', { username, password }, { form: true })
export const getMe = () => request('/users/me')
export const deleteAccount = (password) => request('/users/me', 'DELETE', { password })

export const getFriends = () => request('/friends')
export const removeFriend = (userId) => request(`/friends/${userId}`, 'DELETE')
export const getFriendRequests = () => request('/friends/requests')
export const sendFriendRequest = (username) => request('/friends/requests', 'POST', { username })
export const acceptFriendRequest = (id) => request(`/friends/requests/${id}/accept`, 'POST')
export const deleteFriendRequest = (id) => request(`/friends/requests/${id}`, 'DELETE')

export const getTodos = () => request(BASE)
export const createTodo = (todo) => request(BASE, 'POST', todo)
export const updateTodo = (id, todo) => request(`${BASE}/${id}`, 'PUT', todo)
export const patchTodo = (id, changes) => request(`${BASE}/${id}`, 'PATCH', changes)
export const deleteTodo = (id) => request(`${BASE}/${id}`, 'DELETE')

export const getComments = (todoId) => request(`${BASE}/${todoId}/comments`)
export const createComment = (todoId, body) => request(`${BASE}/${todoId}/comments`, 'POST', { body })
export const deleteComment = (todoId, commentId) => request(`${BASE}/${todoId}/comments/${commentId}`, 'DELETE')
export const getActivities = (todoId) => request(`${BASE}/${todoId}/activities`)
