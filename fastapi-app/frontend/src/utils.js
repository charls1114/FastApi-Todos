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

export const AVATARS = {
  'Soo-jin': 'SJ',
  'Min-jun': 'MJ',
  Hana: 'HA',
  Taeyang: 'TY',
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
    assignee: '',
  }
}

export function payloadOf(todo) {
  const { id: _id, ...rest } = todo
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
  return timePart ? `${Number(month)}/${Number(day)} ${timePart}` : `${Number(month)}/${Number(day)}`
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
  return AVATARS[name] ?? name.slice(0, 2).toUpperCase()
}
