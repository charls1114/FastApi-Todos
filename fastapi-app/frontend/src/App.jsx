import { useCallback, useEffect, useRef, useState } from 'react'
import { getTodos, createTodo, updateTodo, deleteTodo } from './api'
import {
  STATUSES,
  TAG_COLORS,
  TAG_LABELS,
  PRIORITY_COLORS,
  PRIORITY_LABELS,
  emptyTodo,
  payloadOf,
  formatDate,
  formatDateTime,
  isOverdue,
  initials,
} from './utils'

function CardModal({ title, card, status, onSave, onClose }) {
  const [form, setForm] = useState(() => ({ ...emptyTodo(status), ...card }))

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!form.title?.trim()) return
    onSave({
      ...emptyTodo(status),
      ...form,
      title: form.title.trim(),
      description: form.description?.trim() ?? '',
      tag: form.tag || null,
      due_date: form.due_date || '',
    })
  }

  return (
    <div
      className="modal-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="modal-box w-full max-w-md rounded-2xl p-6"
        style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', boxShadow: '0 8px 40px rgba(0,0,0,0.12)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 700, fontSize: '1.1rem', color: '#1a1a2e' }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:bg-black/5 transition-colors"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>제목 *</label>
            <input
              autoFocus
              value={form.title ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="카드 제목을 입력하세요"
              className="w-full rounded-xl px-3.5 py-2.5 text-sm outline-none"
              style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e', fontFamily: 'Inter, sans-serif' }}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>설명</label>
            <textarea
              value={form.description ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="작업에 대한 설명..."
              rows={3}
              className="w-full rounded-xl px-3.5 py-2.5 text-sm outline-none resize-none"
              style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e', fontFamily: 'Inter, sans-serif' }}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>시작 시간</label>
              <input
                type="datetime-local"
                value={form.start_at ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, start_at: e.target.value || null }))}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e' }}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>장소</label>
              <input
                value={form.location ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
                placeholder="예: 새천년관 401호"
                className="w-full rounded-xl px-3.5 py-2.5 text-sm outline-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e', fontFamily: 'Inter, sans-serif' }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>태그</label>
              <select
                value={form.tag ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, tag: e.target.value || null }))}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none appearance-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e' }}
              >
                <option value="">없음</option>
                <option value="hangout">약속</option>
                <option value="work">업무</option>
                <option value="important">중요</option>
                <option value="trip">여행</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>우선순위</label>
              <select
                value={form.priority ?? 'medium'}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none appearance-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e' }}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>담당자</label>
              <input
                value={form.assignee ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, assignee: e.target.value }))}
                placeholder="담당자 이름"
                className="w-full rounded-xl px-3.5 py-2.5 text-sm outline-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e', fontFamily: 'Inter, sans-serif' }}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>마감일</label>
              <input
                type="date"
                value={form.due_date ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e' }}
              />
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors"
              style={{ background: 'rgba(0,0,0,0.06)', color: '#8888a8' }}
            >
              취소
            </button>
            <button
              type="submit"
              className="btn-primary flex-1 py-2.5 rounded-xl text-sm font-semibold"
              style={{ background: '#7c5cfc', color: '#fff' }}
            >
              저장
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function KanbanCard({ todo, colColor, onEdit, onDelete, onDragStart, onDragEnd, isDragging }) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`card-drag card-hover rounded-xl p-4 mb-2.5 last:mb-0 relative group ${isDragging ? 'card-dragging' : ''}`}
      style={{
        background: '#ffffff',
        borderLeft: `3px solid ${colColor}`,
        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      }}
    >
      <div className={`absolute top-3 right-3 flex gap-1 transition-opacity ${hovered ? 'opacity-100' : 'opacity-0'}`}>
        <button
          onClick={(e) => { e.stopPropagation(); onEdit() }}
          className="w-6 h-6 rounded-md flex items-center justify-center text-xs hover:bg-black/5 transition-colors"
          style={{ color: '#8888a8' }}
          title="편집"
        >
          ✎
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          className="w-6 h-6 rounded-md flex items-center justify-center text-xs hover:bg-red-500/20 hover:text-red-400 transition-colors"
          style={{ color: '#8888a8' }}
          title="삭제"
        >
          ✕
        </button>
      </div>

      <div className="flex items-center gap-2 mb-2.5">
        {todo.tag && (
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full tracking-wide ${TAG_COLORS[todo.tag]}`}>
            {TAG_LABELS[todo.tag] ?? todo.tag}
          </span>
        )}
        <span className={`text-[10px] font-medium ${PRIORITY_COLORS[todo.priority] ?? PRIORITY_COLORS.medium}`}>
          {PRIORITY_LABELS[todo.priority] ?? PRIORITY_LABELS.medium}
        </span>
      </div>

      <p className="text-sm font-semibold mb-1.5 pr-10 leading-snug" style={{ color: '#1a1a2e', fontFamily: 'Outfit, sans-serif' }}>
        {todo.title}
      </p>

      {todo.description && (
        <p className="text-xs leading-relaxed mb-2 line-clamp-2" style={{ color: '#8888a8' }}>
          {todo.description}
        </p>
      )}

      {(todo.start_at || todo.location) && (
        <div className="flex flex-col gap-0.5 mb-3">
          {todo.start_at && (
            <span className="text-[10px] flex items-center gap-1" style={{ color: '#8888a8' }}>
              🕒 {formatDateTime(todo.start_at)}
            </span>
          )}
          {todo.location && (
            <span className="text-[10px] flex items-center gap-1" style={{ color: '#8888a8' }}>
              📍 {todo.location}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-1.5">
          <div
            className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold"
            style={{ background: colColor + '33', color: colColor }}
          >
            {initials(todo.assignee)}
          </div>
          <span className="text-[10px]" style={{ color: '#8888a8' }}>{todo.assignee || '미지정'}</span>
        </div>
        {todo.due_date && (
          <span
            className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${isOverdue(todo.due_date) ? 'bg-red-500/15 text-red-400' : 'text-gray-500'}`}
          >
            {isOverdue(todo.due_date) ? '⚠ ' : ''}{formatDate(todo.due_date)}
          </span>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [todos, setTodos] = useState([])
  const [error, setError] = useState(null)
  const [modal, setModal] = useState(null)
  const [search, setSearch] = useState('')
  const dragCard = useRef(null)
  const [draggingId, setDraggingId] = useState(null)
  const [dropTarget, setDropTarget] = useState(null)

  const load = async () => {
    try {
      setTodos(await getTodos())
      setError(null)
    } catch (e) {
      setError(`목록 불러오기 실패: ${e.message}`)
    }
  }

  useEffect(() => { load() }, [])

  const runAction = async (label, job) => {
    try {
      await job()
      setError(null)
    } catch (e) {
      setError(`${label} 실패: ${e.message}`)
    }
  }

  const filtered = todos.filter(
    (t) =>
      !search ||
      t.title.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase())
  )

  const totalCards = todos.length
  const doneCards = todos.filter((t) => t.status === 'done').length

  const handleDragStart = (e, todo) => {
    dragCard.current = todo.id
    setDraggingId(todo.id)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragEnd = () => {
    setDraggingId(null)
    setDropTarget(null)
    dragCard.current = null
  }

  const handleDrop = (e, status) => {
    e.preventDefault()
    const id = dragCard.current
    const todo = todos.find((t) => t.id === id)
    setDropTarget(null)
    setDraggingId(null)
    dragCard.current = null
    if (!todo || todo.status === status) return
    runAction('상태 변경', async () => {
      await updateTodo(id, payloadOf({ ...todo, status }))
      await load()
    })
  }

  const handleSave = useCallback((card) => {
    if (!modal) return
    runAction(modal.mode === 'add' ? '추가' : '수정', async () => {
      if (modal.mode === 'add') {
        await createTodo(payloadOf({ ...emptyTodo(modal.status), ...card, status: modal.status }))
      } else {
        await updateTodo(modal.todo.id, payloadOf({ ...modal.todo, ...card }))
      }
      setModal(null)
      await load()
    })
  }, [modal])

  const handleDelete = (todo) => {
    if (!confirm('정말 삭제할까요?')) return
    runAction('삭제', async () => {
      await deleteTodo(todo.id)
      await load()
    })
  }

  return (
    <div className="min-h-screen" style={{ background: '#f4f4f8' }}>
      <header
        className="sticky top-0 z-40 px-6 py-4 flex items-center justify-between"
        style={{
          background: 'rgba(244,244,248,0.88)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(0,0,0,0.07)',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
            style={{ background: 'linear-gradient(135deg, #7c5cfc, #4ecdc4)', color: '#fff', fontFamily: 'Outfit, sans-serif' }}
          >
            TL
          </div>
          <div>
            <h1 className="text-base font-bold leading-none" style={{ fontFamily: 'Outfit, sans-serif', color: '#1a1a2e' }}>
              Todo-List
            </h1>
            <p className="text-[10px] mt-0.5" style={{ color: '#8888a8' }}>
              {doneCards}/{totalCards} 완료
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs" style={{ color: '#8888a8' }}>⌕</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="카드 검색..."
              className="pl-7 pr-3 py-2 rounded-xl text-sm outline-none w-48 focus:w-56 transition-all"
              style={{
                background: 'rgba(0,0,0,0.04)',
                border: '1px solid rgba(0,0,0,0.06)',
                color: '#1a1a2e',
                fontFamily: 'Inter, sans-serif',
              }}
            />
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl" style={{ background: 'rgba(0,0,0,0.04)', border: '1px solid rgba(0,0,0,0.06)' }}>
            <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(0,0,0,0.06)' }}>
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${totalCards ? (doneCards / totalCards) * 100 : 0}%`, background: '#44cf6c' }}
              />
            </div>
            <span className="text-xs font-medium" style={{ color: '#44cf6c' }}>
              {totalCards ? Math.round((doneCards / totalCards) * 100) : 0}%
            </span>
          </div>
        </div>
      </header>

      {error && <p className="px-6 pt-4 text-sm text-red-600">{error}</p>}

      <main className="px-6 py-6 flex gap-4 overflow-x-auto pb-8" style={{ minHeight: 'calc(100vh - 73px)' }}>
        {STATUSES.map((col) => {
          const cards = filtered.filter((t) => t.status === col.key)
          const isTarget = dropTarget === col.key
          return (
            <div
              key={col.key}
              className={`flex-shrink-0 w-72 flex flex-col rounded-2xl ${isTarget ? 'drop-target' : ''}`}
              style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.07)' }}
              onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setDropTarget(col.key) }}
              onDrop={(e) => handleDrop(e, col.key)}
              onDragLeave={() => setDropTarget(null)}
            >
              <div className="px-4 pt-4 pb-3 rounded-t-2xl" style={{ borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: col.color, boxShadow: `0 0 8px ${col.color}80` }} />
                    <h2 className="text-sm font-bold tracking-wide" style={{ fontFamily: 'Outfit, sans-serif', color: '#1a1a2e' }}>
                      {col.label}
                    </h2>
                  </div>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: col.color + '22', color: col.color }}>
                    {cards.length}
                  </span>
                </div>
              </div>

              <div className="column-scroll flex-1 p-3">
                {cards.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-10 rounded-xl" style={{ border: `1px dashed ${col.color}33`, color: '#8888a8' }}>
                    <span className="text-2xl mb-1" style={{ opacity: 0.4 }}>○</span>
                    <span className="text-xs">여기에 드롭하세요</span>
                  </div>
                )}
                {cards.map((todo) => (
                  <KanbanCard
                    key={todo.id}
                    todo={todo}
                    colColor={col.color}
                    isDragging={draggingId === todo.id}
                    onDragStart={(e) => handleDragStart(e, todo)}
                    onDragEnd={handleDragEnd}
                    onEdit={() => setModal({ mode: 'edit', status: col.key, todo })}
                    onDelete={() => handleDelete(todo)}
                  />
                ))}
              </div>

              <div className="p-3 pt-0">
                <button
                  onClick={() => setModal({ mode: 'add', status: col.key })}
                  className="btn-primary w-full py-2.5 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all"
                  style={{ background: col.color + '18', color: col.color, border: `1px dashed ${col.color}50` }}
                >
                  <span className="text-base leading-none">+</span>
                  카드 추가
                </button>
              </div>
            </div>
          )
        })}
      </main>

      {modal && (
        <CardModal
          title={modal.mode === 'add' ? '새 카드 추가' : '카드 편집'}
          card={modal.todo ?? emptyTodo(modal.status)}
          status={modal.status}
          onSave={handleSave}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}
