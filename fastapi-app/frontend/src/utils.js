export const STATUSES = [
  { key: 'planned', label: '예정', color: '#7c5cfc' },
  { key: 'in_progress', label: '진행중', color: '#f5a623' },
  { key: 'done', label: '완료', color: '#44cf6c' },
]

export const TAG_COLORS = {
  hangout: 'bg-purple-100 text-purple-700 border border-purple-200',
  work: 'bg-blue-100 text-blue-700 border border-blue-200',
  important: 'bg-red-100 text-red-700 border border-red-200',
  trip: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
}

export const TAG_LABELS = {
  hangout: '약속',
  work: '업무',
  important: '중요',
  trip: '여행',
}

export const PRIORITY_COLORS = {
  low: 'text-emerald-600',
  medium: 'text-amber-600',
  high: 'text-red-600',
}

export const PRIORITY_LABELS = {
  low: '↓ Low',
  medium: '→ Medium',
  high: '↑ High',
}

export function emptyTodo(status = 'planned') {
  return {
    title: '',
    description: '',
    start_at: null,
    end_at: null,
    location: '',
    status,
    tag: null,
    priority: 'medium',
    assignee_id: null,
  }
}

// 서버가 채워 주는 필드(id, 작성자, 담당자 정보)는 빼고 보낸다
export function payloadOf(todo) {
  const { id: _id, owner: _owner, assignee: _assignee, assignment_status: _assignmentStatus, ...rest } = todo
  return rest
}

export function formatDate(d) {
  if (!d) return ''
  const date = new Date(d)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function formatDateTime(value) {
  if (!value) return ''
  const [datePart, timePart] = value.split('T')
  const [, month, day] = datePart.split('-')
  return timePart ? `${Number(month)}/${Number(day)} ${timePart.slice(0, 5)}` : `${Number(month)}/${Number(day)}`
}

export function isOverdue(d) {
  if (!d) return false
  return new Date(d) < new Date()
}

export const CHECKLIST_TAGS = ['hangout', 'work', 'important']

// 할일 기간의 끝 시점: 종료 일시를 기준으로 하며, 날짜만 있으면 그날의 끝으로 본다.
export function periodEndOf(todo) {
  const value = todo.end_at
  if (!value) return null
  return new Date(value.includes('T') ? value : `${value}T23:59:59`)
}

export function isPeriodOver(todo, now = new Date()) {
  const end = periodEndOf(todo)
  return end !== null && end < now
}

export function initials(name) {
  if (!name) return '?'
  return name.slice(0, 2).toUpperCase()
}

export const FIELD_LABELS = {
  title: '제목',
  description: '설명',
  start_at: '시작 일시',
  end_at: '종료 일시',
  location: '장소',
  status: '상태',
  tag: '태그',
  priority: '우선순위',
  assignee_id: '담당자',
}

// 활동 기록의 값(문자열)을 화면용으로 바꾼다
export function activityValue(field, value) {
  if (value === null || value === undefined || value === '') return '없음'
  if (field === 'status') return STATUSES.find((item) => item.key === value)?.label ?? value
  if (field === 'tag') return TAG_LABELS[value] ?? value
  if (field === 'priority') return PRIORITY_LABELS[value] ?? value
  if (field === 'start_at' || field === 'end_at') return formatDateTime(value)
  return value
}

export const DELETED_USER = '탈퇴한 사용자'

export function formatTimestamp(value) {
  return new Date(value).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// 알림 종류별 표시. 새 종류는 backend/notifications.py 의 NOTIFICATION_MESSAGES 와 함께 추가한다.
export const NOTIFICATION_TYPES = {
  todo_assigned: { label: '할일 할당', icon: '📥' },
  todo_rejected: { label: '할일 할당 거부', icon: '⛔' },
  todo_accepted: { label: '할일 수락', icon: '✅' },
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

// 알림 발생 시각을 현재 시각 기준으로: 방금 전 / N분 전 / N시간 전 / (하루가 넘으면) N일 전
export function relativeTime(value, now = new Date()) {
  const elapsed = Math.max(0, now - new Date(value))
  if (elapsed < MINUTE) return '방금 전'
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)}분 전`
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)}시간 전`
  return `${Math.floor(elapsed / DAY)}일 전`
}

function dayLabel(date, now) {
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY)
  if (days === 0) return '오늘'
  if (days === 1) return '어제'
  return date.toLocaleDateString('ko-KR', { year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
}

// 알림을 최신순으로 정렬해 (로컬) 날짜별로 묶는다: [{ label: '오늘', items: [...] }, ...]
export function groupByDay(notifications, now = new Date()) {
  const sorted = [...notifications].sort((a, b) => new Date(b.created_at) - new Date(a.created_at) || b.id - a.id)
  const groups = []
  for (const item of sorted) {
    const label = dayLabel(new Date(item.created_at), now)
    if (groups.at(-1)?.label === label) groups.at(-1).items.push(item)
    else groups.push({ label, items: [item] })
  }
  return groups
}

// 다른 사람이 나에게 할당했고 아직 수락하지 않은 할 일
export function isPendingForMe(todo, me) {
  return todo.assignment_status === 'pending' && todo.assignee?.id === me.id && todo.owner.id !== me.id
}

// 나의 기존 일정(내가 맡은 수락된 할 일, 담당자 없이 내가 만든 할 일) 중 기간이 겹치는 것. 완료된 일은 제외한다.
export function findConflicts(todo, todos, me) {
  const start = new Date(todo.start_at)
  const end = new Date(todo.end_at)
  return todos.filter((other) => {
    if (other.id === todo.id || other.status === 'done' || other.assignment_status === 'pending') return false
    const mine = other.assignee ? other.assignee.id === me.id : other.owner.id === me.id
    return mine && new Date(other.start_at) <= end && start <= new Date(other.end_at)
  })
}
