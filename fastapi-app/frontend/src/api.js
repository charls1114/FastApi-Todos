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

// 할당 수락·거부 (거부하면 할 일이 삭제된다)
export const acceptTodo = (todoId) => request(`${BASE}/${todoId}/accept`, 'POST')
export const rejectTodo = (todoId, reason) => request(`${BASE}/${todoId}/reject`, 'POST', { reason })

export const getNotifications = () => request('/notifications')
export const readNotification = (id) => request(`/notifications/${id}/read`, 'POST')
export const readAllNotifications = () => request('/notifications/read-all', 'POST')

// 실시간 알림(SSE) 구독. EventSource 는 Authorization 헤더를 보낼 수 없어 fetch 스트림으로 읽는다.
// 연결이 끊기면 1초부터 최대 30초까지 늘려 가며 다시 연결한다. 반환한 함수를 호출하면 구독을 끝낸다.
// onReady: (재)연결될 때마다 — 끊겨 있던 동안 놓친 알림을 다시 불러오는 데 쓴다. onNotification: 새 알림 { type }
export function subscribeNotifications({ onReady, onNotification }) {
  const controller = new AbortController()
  let retryMs = 1000
  let timer = null

  const dispatch = (block) => {
    let event = 'message'
    const data = []
    for (const line of block.split('\n')) {
      if (!line || line.startsWith(':')) continue          // 주석(keep-alive)
      const colon = line.indexOf(':')
      const field = colon < 0 ? line : line.slice(0, colon)
      const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
      if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    if (event === 'ready') onReady?.()
    else if (event === 'notification') onNotification?.(data.length ? JSON.parse(data.join('\n')) : null)
  }

  const connect = async () => {
    const token = getToken()
    if (!token) return
    try {
      const res = await fetch('/notifications/stream', {
        headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
        signal: controller.signal,
      })
      if (res.status === 401) {                    // 토큰 만료 → 로그인 화면으로
        onUnauthorized()
        return
      }
      if (!res.ok || !res.body) throw new Error(`${res.status}`)
      retryMs = 1000
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer = (buffer + value).replace(/\r\n?/g, '\n')
        let end
        while ((end = buffer.indexOf('\n\n')) >= 0) {
          dispatch(buffer.slice(0, end))
          buffer = buffer.slice(end + 2)
        }
      }
    } catch {
      // 네트워크 오류 — 아래에서 다시 연결한다
    }
    if (controller.signal.aborted) return
    timer = setTimeout(connect, retryMs)
    retryMs = Math.min(retryMs * 2, 30_000)
  }

  connect()
  return () => {
    controller.abort()
    clearTimeout(timer)
  }
}
