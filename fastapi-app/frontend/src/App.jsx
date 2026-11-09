import { useCallback, useEffect, useRef, useState } from 'react'
import {
  getTodos,
  createTodo,
  updateTodo,
  patchTodo,
  deleteTodo,
  getMe,
  deleteAccount,
  getFriends,
  removeFriend,
  getFriendRequests,
  sendFriendRequest,
  acceptFriendRequest,
  deleteFriendRequest,
  login,
  register,
  getToken,
  setToken,
  setUnauthorizedHandler,
  getComments,
  createComment,
  deleteComment,
  getActivities,
  acceptTodo,
  rejectTodo,
  getNotifications,
  readNotification,
  readAllNotifications,
  subscribeNotifications,
} from './api'
import {
  STATUSES,
  TAG_COLORS,
  TAG_LABELS,
  PRIORITY_COLORS,
  PRIORITY_LABELS,
  emptyTodo,
  payloadOf,
  formatDateTime,
  initials,
  CHECKLIST_TAGS,
  periodEndOf,
  isPeriodOver,
  FIELD_LABELS,
  activityValue,
  formatTimestamp,
  DELETED_USER,
  NOTIFICATION_TYPES,
  relativeTime,
  groupByDay,
  isPendingForMe,
  findConflicts,
} from './utils'

const VIEWS = [
  { key: 'board', label: '칸반보드', icon: '▦' },
  { key: 'calendar', label: '달력', icon: '▤' },
]

// 서버는 내가 작성했거나 담당한 할 일만 돌려준다. 그 안에서 다시 거른다.
const SCOPES = [
  { key: 'all', label: '전체' },
  { key: 'assigned', label: '내 할 일' },
  { key: 'owned', label: '내가 만든 일' },
]

const INPUT_STYLE = { background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e', fontFamily: 'Inter, sans-serif' }

function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', display_name: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const isSignup = mode === 'signup'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (isSignup) await register(form)
      const { access_token: token, user } = await login(form.username, form.password)
      setToken(token)
      onLogin(user)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const field = (key) => ({
    value: form[key],
    onChange: (e) => setForm((f) => ({ ...f, [key]: e.target.value })),
    className: 'w-full rounded-xl px-3.5 py-2.5 text-sm outline-none',
    style: INPUT_STYLE,
    required: true,
  })

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: '#f4f4f8' }}>
      <section
        className="w-full max-w-sm rounded-2xl p-6"
        style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.08)', boxShadow: '0 8px 40px rgba(0,0,0,0.06)' }}
        aria-label={isSignup ? '회원가입' : '로그인'}
      >
        <div className="flex items-center gap-3 mb-6">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
            style={{ background: 'linear-gradient(135deg, #7c5cfc, #4ecdc4)', color: '#fff', fontFamily: 'Outfit, sans-serif' }}
          >
            TL
          </div>
          <h1 className="text-base font-bold" style={{ fontFamily: 'Outfit, sans-serif', color: '#1a1a2e' }}>Todo-List</h1>
        </div>

        <div className="auth-tabs" role="tablist">
          {[['login', '로그인'], ['signup', '회원가입']].map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={mode === key}
              className={mode === key ? 'is-active' : ''}
              onClick={() => { setMode(key); setError(null) }}
            >
              {label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-3 mt-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }} htmlFor="auth-username">아이디</label>
            <input id="auth-username" autoComplete="username" placeholder="영문, 숫자, _ (3~30자)" {...field('username')} />
          </div>
          {isSignup && (
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }} htmlFor="auth-name">이름</label>
              <input id="auth-name" autoComplete="nickname" placeholder="다른 사용자에게 보이는 이름" maxLength={50} {...field('display_name')} />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }} htmlFor="auth-password">비밀번호</label>
            <input
              id="auth-password"
              type="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              placeholder={isSignup ? '8자 이상' : ''}
              minLength={isSignup ? 8 : undefined}
              {...field('password')}
            />
          </div>
          {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="btn-primary w-full py-2.5 rounded-xl text-sm font-semibold disabled:opacity-60"
            style={{ background: '#7c5cfc', color: '#fff' }}
          >
            {isSignup ? '가입하고 시작하기' : '로그인'}
          </button>
        </form>
      </section>
    </div>
  )
}

function TodoDiscussion({ todoId, me }) {
  const [tab, setTab] = useState('comments')
  const [comments, setComments] = useState([])
  const [activities, setActivities] = useState([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false
    Promise.all([getComments(todoId), getActivities(todoId)])
      .then(([loadedComments, loadedActivities]) => {
        if (ignore) return
        setComments(loadedComments)
        setActivities(loadedActivities)
      })
      .catch((err) => !ignore && setError(err.message))
    return () => { ignore = true }
  }, [todoId])

  const handleComment = async (e) => {
    e.preventDefault()
    if (!draft.trim()) return
    try {
      const comment = await createComment(todoId, draft)
      setComments((current) => [...current, comment])
      setDraft('')
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDeleteComment = async (comment) => {
    try {
      await deleteComment(todoId, comment.id)
      setComments((current) => current.filter((item) => item.id !== comment.id))
    } catch (err) {
      setError(err.message)
    }
  }

  const describe = (activity) => {
    if (activity.action === 'created') return '할 일을 만들었습니다'
    const label = FIELD_LABELS[activity.field] ?? activity.field
    if (activity.field === 'description') return `${label}을 바꿨습니다`
    return `${label}: ${activityValue(activity.field, activity.old_value)} → ${activityValue(activity.field, activity.new_value)}`
  }

  return (
    <section className="discussion" aria-label="댓글과 활동 기록">
      <div className="auth-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'comments'} className={tab === 'comments' ? 'is-active' : ''} onClick={() => setTab('comments')}>
          댓글 {comments.length}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'activity'} className={tab === 'activity' ? 'is-active' : ''} onClick={() => setTab('activity')}>
          활동 기록
        </button>
      </div>

      {error && <p role="alert" className="text-xs text-red-600 mt-2">{error}</p>}

      {tab === 'comments' ? (
        <>
          <ul className="discussion-list">
            {comments.length === 0 && <li className="discussion-empty">아직 댓글이 없습니다.</li>}
            {comments.map((comment) => (
              <li key={comment.id} className="comment-item">
                <div className="comment-meta">
                  <strong>{comment.author?.display_name ?? DELETED_USER}</strong>
                  <time dateTime={comment.created_at}>{formatTimestamp(comment.created_at)}</time>
                  {comment.author?.id === me.id && (
                    <button type="button" onClick={() => handleDeleteComment(comment)} aria-label="댓글 삭제">삭제</button>
                  )}
                </div>
                <p>{comment.body}</p>
              </li>
            ))}
          </ul>
          <form onSubmit={handleComment} className="flex gap-2 mt-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="댓글을 입력하세요"
              maxLength={1000}
              className="flex-1 rounded-xl px-3 py-2 text-sm outline-none"
              style={INPUT_STYLE}
            />
            <button type="submit" className="px-3 py-2 rounded-xl text-xs font-semibold" style={{ background: '#7c5cfc', color: '#fff' }}>
              등록
            </button>
          </form>
        </>
      ) : (
        <ul className="discussion-list">
          {activities.map((activity) => (
            <li key={activity.id} className="activity-item">
              <span><strong>{activity.actor?.display_name ?? DELETED_USER}</strong> · {describe(activity)}</span>
              <time dateTime={activity.created_at}>{formatTimestamp(activity.created_at)}</time>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function CardModal({ title, card, status, friends, me, onSave, onClose, onRespond }) {
  const [form, setForm] = useState(() => ({ ...emptyTodo(status), ...card }))
  const [dateError, setDateError] = useState(null)
  // 담당자는 본인 또는 친구만 고를 수 있다. 친구를 끊은 기존 담당자도 그대로 보이도록 목록에 남긴다.
  const assignees = [me, ...friends]
  if (card.assignee && !assignees.some((user) => user.id === card.assignee.id)) assignees.push(card.assignee)
  const canChangeAssignee = !card.id || card.owner?.id === me.id

  useEffect(() => {
    const handleKeyDown = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!form.title?.trim() || !form.start_at || !form.end_at) return
    if (form.end_at < form.start_at) {
      setDateError('종료 일시는 시작 일시 이후여야 합니다.')
      return
    }
    onSave({
      ...emptyTodo(status),
      ...form,
      title: form.title.trim(),
      description: form.description?.trim() ?? '',
      tag: form.tag || null,
    })
  }

  return (
    <div
      className="modal-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
    >
      <button
        type="button"
        aria-label="모달 닫기"
        tabIndex={-1}
        onClick={onClose}
        className="absolute inset-0 w-full h-full cursor-default"
      />
      <dialog
        open
        aria-modal="true"
        aria-label={title}
        className="modal-box relative w-full max-w-md max-h-[90vh] overflow-y-auto rounded-2xl p-6 text-inherit"
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

        {card.id && isPendingForMe(card, me) && (
          <div className="pending-notice">
            <span>{card.owner.display_name}님이 배정한 할일입니다. 아직 수락하지 않았습니다.</span>
            <button type="button" className="friend-action is-primary" onClick={onRespond}>수락/거부</button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>제목 *</label>
            <input
              autoFocus
              value={form.title ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="할일 제목을 입력하세요"
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
              placeholder="할일에 대한 설명..."
              rows={3}
              className="w-full rounded-xl px-3.5 py-2.5 text-sm outline-none resize-none"
              style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e', fontFamily: 'Inter, sans-serif' }}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>시작 일시 *</label>
              <input
                type="datetime-local"
                required
                value={form.start_at ?? ''}
                onChange={(e) => { setDateError(null); setForm((f) => ({ ...f, start_at: e.target.value || null })) }}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e' }}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>장소</label>
              <input
                value={form.location ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
                placeholder="예: 아담샬관 401호"
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
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }} htmlFor="card-assignee">담당자</label>
              <select
                id="card-assignee"
                value={form.assignee_id ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, assignee_id: e.target.value ? Number(e.target.value) : null }))}
                disabled={!canChangeAssignee}
                title={canChangeAssignee ? undefined : '담당자는 작성자만 바꿀 수 있습니다'}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none appearance-none disabled:opacity-60"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e' }}
              >
                <option value="">미지정</option>
                {assignees.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name} (@{user.username}){user.id === me.id ? ' · 나' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }}>종료 일시 *</label>
              <input
                type="datetime-local"
                required
                min={form.start_at ?? undefined}
                value={form.end_at ?? ''}
                onChange={(e) => { setDateError(null); setForm((f) => ({ ...f, end_at: e.target.value || null })) }}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none"
                style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', color: '#1a1a2e' }}
              />
            </div>
          </div>

          {dateError && <p role="alert" className="text-xs text-red-600">{dateError}</p>}

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

        {card.id && (
          <>
            <p className="text-[11px] mt-4" style={{ color: '#8888a8' }}>작성자: {card.owner?.display_name}</p>
            <TodoDiscussion todoId={card.id} me={me} />
          </>
        )}
      </dialog>
    </div>
  )
}

function ModalShell({ title, onClose, children }) {
  useEffect(() => {
    const handleKeyDown = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div
      className="modal-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
    >
      <button
        type="button"
        aria-label="모달 닫기"
        tabIndex={-1}
        onClick={onClose}
        className="absolute inset-0 w-full h-full cursor-default"
      />
      <dialog
        open
        aria-modal="true"
        aria-label={title}
        className="modal-box relative w-full max-w-md max-h-[90vh] overflow-y-auto rounded-2xl p-6 text-inherit"
        style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.1)', boxShadow: '0 8px 40px rgba(0,0,0,0.12)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold" style={{ fontFamily: 'Outfit, sans-serif', color: '#1a1a2e' }}>{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:bg-black/5 transition-colors"
          >
            ✕
          </button>
        </div>
        {children}
      </dialog>
    </div>
  )
}

function FriendRow({ user, children }) {
  return (
    <li className="friend-row">
      <span className="user-avatar" aria-hidden="true">{initials(user.display_name)}</span>
      <span className="friend-name">
        <strong>{user.display_name}</strong> <span>@{user.username}</span>
      </span>
      {children}
    </li>
  )
}

// 친구 요청 보내기·받은 요청 수락/거절·보낸 요청 취소·친구 끊기
function FriendsModal({ friends, requests, onChange, onClose }) {
  const [username, setUsername] = useState('')
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  const run = async (job, success) => {
    try {
      await job()
      setError(null)
      setMessage(success ?? null)
      await onChange()
    } catch (err) {
      setMessage(null)
      setError(err.message)
    }
  }

  const handleSend = (e) => {
    e.preventDefault()
    const target = username.trim()
    if (!target) return
    run(async () => {
      await sendFriendRequest(target)
      setUsername('')
    }, `@${target} 님에게 친구 요청을 보냈습니다.`)
  }

  const handleRemove = (friend) => {
    if (!confirm(`${friend.display_name} 님과 친구를 끊을까요? 이미 맡긴 할 일의 담당자는 그대로 유지됩니다.`)) return
    run(() => removeFriend(friend.id))
  }

  return (
    <ModalShell title="친구" onClose={onClose}>
      <form onSubmit={handleSend} className="flex gap-2">
        <input
          aria-label="친구 아이디"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="친구의 아이디를 입력하세요"
          maxLength={30}
          className="flex-1 rounded-xl px-3 py-2 text-sm outline-none"
          style={INPUT_STYLE}
        />
        <button type="submit" className="px-3 py-2 rounded-xl text-xs font-semibold" style={{ background: '#7c5cfc', color: '#fff' }}>
          친구 요청
        </button>
      </form>
      {error && <p role="alert" className="text-xs text-red-600 mt-2">{error}</p>}
      {message && <p role="status" className="text-xs mt-2" style={{ color: '#44a35c' }}>{message}</p>}

      {requests.received.length > 0 && (
        <section className="friend-section" aria-label="받은 친구 요청">
          <h3>받은 요청 {requests.received.length}</h3>
          <ul>
            {requests.received.map((request) => (
              <FriendRow key={request.id} user={request.user}>
                <button type="button" className="friend-action is-primary" onClick={() => run(() => acceptFriendRequest(request.id))}>수락</button>
                <button type="button" className="friend-action" onClick={() => run(() => deleteFriendRequest(request.id))}>거절</button>
              </FriendRow>
            ))}
          </ul>
        </section>
      )}

      <section className="friend-section" aria-label="친구 목록">
        <h3>친구 {friends.length}</h3>
        {friends.length === 0 ? (
          <p className="discussion-empty text-xs">아직 친구가 없습니다. 친구가 되면 할 일의 담당자로 지정할 수 있습니다.</p>
        ) : (
          <ul>
            {friends.map((friend) => (
              <FriendRow key={friend.id} user={friend}>
                <button type="button" className="friend-action" onClick={() => handleRemove(friend)}>친구 끊기</button>
              </FriendRow>
            ))}
          </ul>
        )}
      </section>

      {requests.sent.length > 0 && (
        <section className="friend-section" aria-label="보낸 친구 요청">
          <h3>보낸 요청 {requests.sent.length}</h3>
          <ul>
            {requests.sent.map((request) => (
              <FriendRow key={request.id} user={request.user}>
                <span className="text-[10.5px]" style={{ color: '#8888a8' }}>수락 대기</span>
                <button type="button" className="friend-action" onClick={() => run(() => deleteFriendRequest(request.id))}>취소</button>
              </FriendRow>
            ))}
          </ul>
        </section>
      )}
    </ModalShell>
  )
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  )
}

// 헤더 우측 상단의 종 모양 알림 버튼과 드롭다운 목록
function NotificationBell({ notifications, pendingCount, now, onRead, onReadAll, onOpenTodo, onOpenPending }) {
  const [open, setOpen] = useState(false)
  const [expandedId, setExpandedId] = useState(null)   // 거부 사유를 펼친 알림
  const rootRef = useRef(null)
  const unread = notifications.filter((item) => item.status === 'unread').length

  useEffect(() => {
    if (!open) return undefined
    const handlePointer = (e) => rootRef.current && !rootRef.current.contains(e.target) && setOpen(false)
    const handleKeyDown = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', handlePointer)
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointer)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const handleClick = (item) => {
    if (item.status === 'unread') onRead(item)
    if (item.type === 'todo_rejected') {
      setExpandedId((current) => current === item.id ? null : item.id)
    } else if (item.todo_id) {
      setOpen(false)
      onOpenTodo(item.todo_id)
    }
  }

  return (
    <div className="notification-root" ref={rootRef}>
      <button
        type="button"
        className="notification-bell"
        aria-label={unread ? `알림, 미확인 ${unread}개` : '알림'}
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((value) => !value)}
      >
        <BellIcon />
        {unread > 0 && <span className="notification-badge" aria-hidden="true">{unread > 99 ? '99+' : unread}</span>}
      </button>

      {open && (
        <div className="notification-dropdown" role="region" aria-label="알림 목록">
          <div className="notification-head">
            <h2>알림</h2>
            {unread > 0 && <button type="button" onClick={onReadAll}>모두 읽음</button>}
          </div>

          {pendingCount > 0 && (
            <button type="button" className="notification-pending" onClick={() => { setOpen(false); onOpenPending() }}>
              응답 대기 중인 할일 {pendingCount}개 →
            </button>
          )}

          {notifications.length === 0 ? (
            <p className="notification-empty">알림이 없습니다.</p>
          ) : (
            <div className="notification-scroll">
              {groupByDay(notifications, now).map((group) => (
                <section key={group.label} className="notification-group">
                  <h3>{group.label}</h3>
                  <ul>
                    {group.items.map((item) => {
                      const type = NOTIFICATION_TYPES[item.type]
                      const expanded = expandedId === item.id
                      return (
                        <li key={item.id}>
                          <button
                            type="button"
                            className={`notification-item ${item.status === 'unread' ? 'is-unread' : ''}`}
                            onClick={() => handleClick(item)}
                            aria-expanded={item.type === 'todo_rejected' ? expanded : undefined}
                          >
                            <span className="notification-icon" aria-hidden="true">{type?.icon ?? '🔔'}</span>
                            <span className="notification-body">
                              <span className="notification-message">{item.message}</span>
                              {item.todo_title && <span className="notification-title">{item.todo_title}</span>}
                              <time dateTime={item.created_at} title={formatTimestamp(item.created_at)}>
                                {type?.label ?? item.type} · {relativeTime(item.created_at, now)}
                              </time>
                            </span>
                            {item.status === 'unread' && <span className="notification-dot" aria-label="미확인" />}
                          </button>
                          {expanded && (
                            <div className="notification-reason">
                              <strong>거부 사유</strong>
                              <p>{item.reason}</p>
                            </div>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AssignmentItem({ todo, todos, me, onAccept, onReject }) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const conflicts = findConflicts(todo, todos, me)

  const run = async (job) => {
    setBusy(true)
    setError(null)
    try {
      await job()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const handleReject = (e) => {
    e.preventDefault()
    if (!reason.trim()) return
    run(() => onReject(todo, reason.trim()))
  }

  return (
    <li className="assignment-item">
      <div className="assignment-head">
        <strong>{todo.title}</strong>
        <span>from {todo.owner.display_name}</span>
      </div>
      <p className="assignment-period">
        🕒 {formatDateTime(todo.start_at)} ~ {formatDateTime(todo.end_at)}
        {todo.location && <> · 📍 {todo.location}</>}
      </p>
      {todo.description && <p className="assignment-description">{todo.description}</p>}

      {conflicts.length > 0 && (
        <div className="assignment-conflict" role="note">
          <strong>⚠ 기존 일정과 기간이 겹칩니다</strong>
          <ul>
            {conflicts.map((other) => (
              <li key={other.id}>{other.title} ({formatDateTime(other.start_at)} ~ {formatDateTime(other.end_at)})</li>
            ))}
          </ul>
        </div>
      )}

      {rejecting ? (
        <form onSubmit={handleReject} className="assignment-reject">
          <label htmlFor={`reject-reason-${todo.id}`}>거부 사유 *</label>
          <textarea
            id={`reject-reason-${todo.id}`}
            autoFocus
            required
            rows={2}
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={conflicts.length ? `예: '${conflicts[0].title}' 일정과 겹쳐요` : '거부하는 이유를 입력하세요'}
            style={INPUT_STYLE}
          />
          <div className="assignment-actions">
            <button type="button" className="friend-action" onClick={() => setRejecting(false)} disabled={busy}>취소</button>
            <button type="submit" className="friend-action is-danger" disabled={busy || !reason.trim()}>거부 보내기</button>
          </div>
        </form>
      ) : (
        <div className="assignment-actions">
          <button type="button" className="friend-action" onClick={() => setRejecting(true)} disabled={busy}>거부</button>
          <button type="button" className="friend-action is-primary" onClick={() => run(() => onAccept(todo))} disabled={busy}>수락</button>
        </div>
      )}
      {error && <p role="alert" className="text-xs text-red-600 mt-1">{error}</p>}
    </li>
  )
}

// 로그인 시(또는 알림에서) 열리는 할당 응답 모달: 새로 할당된 할일과 아직 응답하지 않은 할일
function AssignmentModal({ pending, newIds, todos, me, onAccept, onReject, onClose }) {
  const fresh = pending.filter((todo) => newIds.has(todo.id))
  const waiting = pending.filter((todo) => !newIds.has(todo.id))
  const item = (todo) => <AssignmentItem key={todo.id} todo={todo} todos={todos} me={me} onAccept={onAccept} onReject={onReject} />

  return (
    <ModalShell title="할당된 할일 확인" onClose={onClose}>
      {fresh.length > 0 && (
        <section className="friend-section" aria-label="새로 할당된 할일">
          <h3>새로 할당된 할일 {fresh.length}</h3>
          <ul>{fresh.map(item)}</ul>
        </section>
      )}
      {waiting.length > 0 && (
        <section className="friend-section" aria-label="응답 대기 중인 할일">
          <h3>응답 대기 중인 할일 {waiting.length}</h3>
          <ul>{waiting.map(item)}</ul>
        </section>
      )}
      <button type="button" onClick={onClose} className="w-full mt-4 py-2.5 rounded-xl text-sm font-medium" style={{ background: 'rgba(0,0,0,0.06)', color: '#8888a8' }}>
        나중에 하기
      </button>
    </ModalShell>
  )
}

function DeleteAccountModal({ onDeleted, onClose }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await deleteAccount(password)
      onDeleted()
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <ModalShell title="회원 탈퇴" onClose={onClose}>
      <ul className="delete-notice">
        <li>내가 만든 할 일과 그 댓글·활동 기록이 모두 삭제됩니다.</li>
        <li>내가 담당자인 다른 사람의 할 일은 담당자가 비워집니다.</li>
        <li>다른 사람의 할 일에 남긴 댓글과 활동 기록은 &lsquo;{DELETED_USER}&rsquo;로 표시됩니다.</li>
        <li>친구 관계와 친구 요청, 받은 알림이 모두 삭제되며, 되돌릴 수 없습니다.</li>
      </ul>
      <form onSubmit={handleSubmit} className="space-y-3 mt-4">
        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: '#8888a8' }} htmlFor="delete-password">비밀번호 확인</label>
          <input
            id="delete-password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => { setError(null); setPassword(e.target.value) }}
            className="w-full rounded-xl px-3.5 py-2.5 text-sm outline-none"
            style={INPUT_STYLE}
          />
        </div>
        {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
        <div className="flex gap-2">
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-xl text-sm font-medium" style={{ background: 'rgba(0,0,0,0.06)', color: '#8888a8' }}>
            취소
          </button>
          <button type="submit" disabled={submitting} className="flex-1 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-60" style={{ background: '#e5484d', color: '#fff' }}>
            탈퇴하기
          </button>
        </div>
      </form>
    </ModalShell>
  )
}

function KanbanCard({ todo, me, colColor, onEdit, onDelete, onDragStart, onDragEnd, isDragging }) {
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
        {todo.owner.id === me.id && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="w-6 h-6 rounded-md flex items-center justify-center text-xs hover:bg-red-500/20 hover:text-red-400 transition-colors"
            style={{ color: '#8888a8' }}
            title="삭제"
          >
            ✕
          </button>
        )}
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
        {todo.assignment_status === 'pending' && <span className="pending-badge">수락 대기</span>}
      </div>

      <p className="text-sm font-semibold mb-1.5 pr-10 leading-snug" style={{ color: '#1a1a2e', fontFamily: 'Outfit, sans-serif' }}>
        {todo.title}
      </p>

      {todo.description && (
        <p className="text-xs leading-relaxed mb-2 line-clamp-2" style={{ color: '#8888a8' }}>
          {todo.description}
        </p>
      )}

      {(todo.start_at || todo.end_at || todo.location) && (
        <div className="flex flex-col gap-0.5 mb-3">
          {(todo.start_at || todo.end_at) && (
            <span className="text-[10px] flex items-center gap-1" style={{ color: '#8888a8' }}>
              🕒 {todo.start_at ? formatDateTime(todo.start_at) : ''}
              {todo.start_at && todo.end_at ? ' ~ ' : ''}
              {todo.end_at ? formatDateTime(todo.end_at) : ''}
            </span>
          )}
          {todo.location && (
            <span className="text-[10px] flex items-center gap-1" style={{ color: '#8888a8' }}>
              📍 {todo.location}
            </span>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 mt-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <div
            className="w-5 h-5 flex-shrink-0 rounded-full flex items-center justify-center text-[9px] font-bold"
            style={{ background: colColor + '33', color: colColor }}
          >
            {initials(todo.assignee?.display_name)}
          </div>
          <span className="text-[10px] whitespace-nowrap" style={{ color: '#8888a8' }}>{todo.assignee?.display_name ?? '미지정'}</span>
        </div>
        {todo.owner.id !== me.id && (
          <span className="text-[10px] whitespace-nowrap" style={{ color: '#8888a8' }} title={`작성자: ${todo.owner.display_name}`}>
            from {todo.owner.display_name}
          </span>
        )}
      </div>
    </div>
  )
}

function dateKey(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function CalendarView({ todos, month, onMonthChange, onEdit, onAdd }) {
  const [expandedDate, setExpandedDate] = useState(null)
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1)
  const dayCount = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  const gridStart = new Date(month.getFullYear(), month.getMonth(), 1 - firstDay.getDay())
  const gridLength = Math.ceil((firstDay.getDay() + dayCount) / 7) * 7
  const days = Array.from({ length: gridLength }, (_, index) => {
    const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index)
    return { date, key: dateKey(date) }
  })
  const eventsByDate = new Map(days.map(({ key }) => [key, []]))
  const undatedTodos = []

  todos.forEach((todo) => {
    const start = todo.start_at?.slice(0, 10) || ''
    const end = todo.end_at?.slice(0, 10) || ''
    if (!start && !end) {
      undatedTodos.push(todo)
      return
    }

    const rangeStart = start || end
    const rangeEnd = start && end >= start ? end : rangeStart

    days.forEach(({ key }) => {
      if (key >= rangeStart && key <= rangeEnd) {
        eventsByDate.get(key).push({ todo, isStart: key === start, isEnd: key === end })
      }
    })
  })

  const today = dateKey(new Date())

  return (
    <section className="calendar-view" aria-label="할 일 달력">
      <div className="calendar-toolbar">
        <div className="calendar-month-nav">
          <button type="button" className="calendar-nav-button" onClick={() => onMonthChange(-1)} title="이전 달" aria-label="이전 달">‹</button>
          <h2>{month.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long' })}</h2>
          <button type="button" className="calendar-nav-button" onClick={() => onMonthChange(1)} title="다음 달" aria-label="다음 달">›</button>
          <button type="button" className="calendar-today-button" onClick={() => onMonthChange(0)}>오늘</button>
        </div>
        <button type="button" className="calendar-create-button" onClick={() => onAdd(null)}>+ 할일 추가</button>
      </div>

      <div className="calendar-scroll">
        <div className="calendar-grid">
          {['일', '월', '화', '수', '목', '금', '토'].map((weekday) => (
            <div className="calendar-weekday" key={weekday}>{weekday}</div>
          ))}
          {days.map(({ date, key }) => {
            const events = eventsByDate.get(key)
            const isCurrentMonth = date.getMonth() === month.getMonth()
            const isExpanded = expandedDate === key
            const visibleEvents = isExpanded ? events : events.slice(0, 3)

            return (
              <div className={`calendar-day ${isCurrentMonth ? '' : 'is-outside'} ${key === today ? 'is-today' : ''}`} key={key}>
                <div className="calendar-day-heading">
                  <span className="calendar-day-number">{date.getDate()}</span>
                  <button
                    type="button"
                    className="calendar-add-button"
                    onClick={() => onAdd(key)}
                    title={`${key}에 할일 추가`}
                    aria-label={`${key}에 할일 추가`}
                  >+</button>
                </div>
                <div className="calendar-events">
                  {visibleEvents.map(({ todo, isStart, isEnd }, index) => {
                    const status = STATUSES.find((item) => item.key === todo.status)
                    const startTime = todo.start_at?.slice(11, 16)
                    const endTime = todo.end_at?.slice(11, 16)
                    return (
                      <button
                        type="button"
                        className={`calendar-event ${todo.status === 'done' ? 'is-done' : ''}`}
                        key={`${todo.id}-${isStart ? 'start' : ''}-${isEnd ? 'end' : ''}-${index}`}
                        onClick={() => onEdit(todo)}
                        title={`${todo.title}${isStart ? ' · 시작' : ''}${isEnd ? ' · 종료' : ''}`}
                        style={{ '--event-color': status?.color ?? '#7c5cfc' }}
                      >
                        {isStart && startTime && <span className="calendar-event-time">시작 {startTime}</span>}
                        {isEnd && endTime && <span className="calendar-event-deadline">종료 {endTime}</span>}
                        <span className="calendar-event-title">{todo.title}</span>
                      </button>
                    )
                  })}
                  {events.length > 3 && (
                    <button
                      type="button"
                      className="calendar-more-button"
                      onClick={() => setExpandedDate(isExpanded ? null : key)}
                    >
                      {isExpanded ? '접기' : `+ ${events.length - 3}개 더보기`}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {undatedTodos.length > 0 && (
        <section className="calendar-undated">
          <div className="calendar-undated-heading">
            <h3>날짜 미지정</h3>
            <span>{undatedTodos.length}</span>
          </div>
          <div className="calendar-undated-list">
            {undatedTodos.map((todo) => {
              const status = STATUSES.find((item) => item.key === todo.status)
              return (
                <button type="button" className="calendar-undated-item" key={todo.id} onClick={() => onEdit(todo)}>
                  <span className="calendar-status-dot" style={{ background: status?.color ?? '#7c5cfc' }} />
                  <span>{todo.title}</span>
                  <small>{status?.label ?? '예정'}</small>
                </button>
              )
            })}
          </div>
        </section>
      )}
    </section>
  )
}

function ChecklistPanel({ todos, now, onToggle, onEdit }) {
  const items = todos
    .filter((todo) => CHECKLIST_TAGS.includes(todo.tag) && !isPeriodOver(todo, now))
    .sort((a, b) => {
      const aEnd = periodEndOf(a)
      const bEnd = periodEndOf(b)
      if (!aEnd || !bEnd) return aEnd ? -1 : bEnd ? 1 : 0
      return aEnd - bEnd
    })
  const doneCount = items.filter((todo) => todo.status === 'done').length

  return (
    <section className="checklist-panel" aria-label="할일 체크리스트">
      <div className="checklist-heading">
        <h2>체크리스트</h2>
        <span>{doneCount}/{items.length} 완료</span>
      </div>
      <div className="checklist-tags">
        {CHECKLIST_TAGS.map((tag) => (
          <span key={tag} className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TAG_COLORS[tag]}`}>
            {TAG_LABELS[tag]}
          </span>
        ))}
      </div>

      {items.length === 0 ? (
        <p className="checklist-empty">표시할 할일이 없습니다.</p>
      ) : (
        <ul className="checklist-list">
          {items.map((todo) => {
            const isDone = todo.status === 'done'
            return (
              <li key={todo.id} className={`checklist-item ${isDone ? 'is-done' : ''}`}>
                <input
                  type="checkbox"
                  checked={isDone}
                  onChange={() => onToggle(todo)}
                  aria-label={`${todo.title} 완료 표시`}
                />
                <button type="button" className="checklist-body" onClick={() => onEdit(todo)}>
                  <span className="checklist-title">{todo.title}</span>
                  {(todo.start_at || todo.end_at) && (
                    <span className="checklist-period">
                      {todo.start_at ? formatDateTime(todo.start_at) : ''}
                      {todo.start_at && todo.end_at ? ' ~ ' : ''}
                      {todo.end_at ? formatDateTime(todo.end_at) : ''}
                    </span>
                  )}
                </button>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${TAG_COLORS[todo.tag]}`}>
                  {TAG_LABELS[todo.tag]}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function Board({ me, onLogout }) {
  const [todos, setTodos] = useState([])
  const [friends, setFriends] = useState([])
  const [friendRequests, setFriendRequests] = useState({ received: [], sent: [] })
  const [panel, setPanel] = useState(null)       // "friends", "delete-account", "assignments"
  const [scope, setScope] = useState('all')
  const [error, setError] = useState(null)
  const [modal, setModal] = useState(null)
  const [search, setSearch] = useState('')
  const [view, setView] = useState(() => {
    try {
      return localStorage.getItem('todo-view') === 'calendar' ? 'calendar' : 'board'
    } catch {
      return 'board'
    }
  })
  const [calendarMonth, setCalendarMonth] = useState(() => {
    try {
      const savedMonth = localStorage.getItem('todo-calendar-month')
      if (!savedMonth) return new Date()
      const [year, month] = savedMonth.split('-').map(Number)
      return Number.isInteger(year) && month >= 1 && month <= 12
        ? new Date(year, month - 1, 1)
        : new Date()
    } catch {
      return new Date()
    }
  })
  const dragCard = useRef(null)
  const [draggingId, setDraggingId] = useState(null)
  const [dropTarget, setDropTarget] = useState(null)
  const [now, setNow] = useState(() => new Date())
  const [notifications, setNotifications] = useState([])
  const seenNotificationId = useRef(0)            // 마지막으로 받은 알림 id — 새 알림이 오면 할 일 목록도 다시 받는다

  // 기간이 지난 할일이 새로고침 없이도 체크리스트에서 사라지도록 주기적으로 현재 시각을 갱신
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30_000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    let ignore = false
    Promise.all([getTodos(), getFriends(), getFriendRequests(), getNotifications()])
      .then(([loadedTodos, loadedFriends, loadedRequests, loadedNotifications]) => {
        if (ignore) return
        setTodos(loadedTodos)
        setFriends(loadedFriends)
        setFriendRequests(loadedRequests)
        setNotifications(loadedNotifications)
        seenNotificationId.current = loadedNotifications[0]?.id ?? 0
        // 로그인 직후 응답하지 않은 할당이 있으면 모달로 먼저 보여준다
        if (loadedTodos.some((todo) => isPendingForMe(todo, me))) setPanel((current) => current ?? 'assignments')
        setError(null)
      })
      .catch((e) => !ignore && setError(`목록 불러오기 실패: ${e.message}`))
    return () => { ignore = true }
  },[me])

  // 친구가 할당·수락·거부하면 서버가 바로 알려 준다(SSE). 알림을 받거나 다시 연결되면 목록을 새로 받는다.
  useEffect(() => {
    let ignore = false
    const refresh = async () => {
      try {
        const loaded = await getNotifications()
        if (ignore) return
        setNotifications(loaded)
        const latest = loaded[0]?.id ?? 0
        if (latest > seenNotificationId.current) {   // 새 알림 = 할 일이 할당·수락·거부됨 → 할 일 목록도 갱신
          seenNotificationId.current = latest
          const loadedTodos = await getTodos()
          if (!ignore) setTodos(loadedTodos)
        }
      } catch {
        // 일시적인 오류는 다음 알림이나 재연결 때 다시 맞춘다
      }
    }
    const unsubscribe = subscribeNotifications({ onReady: refresh, onNotification: refresh })
    return () => { ignore = true; unsubscribe() }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem('todo-view', view)
    } catch {
      return
    }
  }, [view])

  useEffect(() => {
    try {
      const month = String(calendarMonth.getMonth() + 1).padStart(2, '0')
      localStorage.setItem('todo-calendar-month', `${calendarMonth.getFullYear()}-${month}`)
    } catch {
      return
    }
  }, [calendarMonth])

  const reloadFriends = async () => {
    const [loadedFriends, loadedRequests] = await Promise.all([getFriends(), getFriendRequests()])
    setFriends(loadedFriends)
    setFriendRequests(loadedRequests)
  }

  const runAction = async (label, job) => {
    try {
      await job()
      setError(null)
    } catch (e) {
      setError(`${label} 실패: ${e.message}`)
    }
  }

  const pendingTodos = todos.filter((todo) => isPendingForMe(todo, me))
  // 아직 확인하지 않은 할당 알림이 가리키는 할 일 = 새로 할당된 할 일
  const newAssignmentIds = new Set(
    notifications.filter((item) => item.type === 'todo_assigned' && item.status === 'unread').map((item) => item.todo_id),
  )

  const handleAccept = async (todo) => {
    const savedTodo = await acceptTodo(todo.id)
    setTodos((current) => current.map((item) => item.id === savedTodo.id ? savedTodo : item))
    if (pendingTodos.length <= 1) setPanel((current) => current === 'assignments' ? null : current)   // 마지막 응답이면 모달을 닫는다
  }

  const handleReject = async (todo, reason) => {
    await rejectTodo(todo.id, reason)
    setTodos((current) => current.filter((item) => item.id !== todo.id))
    setModal((current) => current?.todo?.id === todo.id ? null : current)
    if (pendingTodos.length <= 1) setPanel((current) => current === 'assignments' ? null : current)   // 마지막 응답이면 모달을 닫는다
  }

  const handleReadNotification = (item) => runAction('알림 확인', async () => {
    const saved = await readNotification(item.id)
    setNotifications((current) => current.map((n) => n.id === saved.id ? saved : n))
  })

  const handleReadAll = () => runAction('알림 확인', async () => {
    await readAllNotifications()
    setNotifications((current) => current.map((n) => ({ ...n, status: 'read' })))
  })

  const openTodoById = (todoId) => {
    const todo = todos.find((item) => item.id === todoId)
    if (!todo) return
    if (isPendingForMe(todo, me)) setPanel('assignments')
    else setModal({ mode: 'edit', status: todo.status, todo })
  }

  const filtered = todos.filter(
    (t) =>
      (scope !== 'assigned' || t.assignee?.id === me.id) &&
      (scope !== 'owned' || t.owner.id === me.id) &&
      (!search ||
        t.title.toLowerCase().includes(search.toLowerCase()) ||
        t.description.toLowerCase().includes(search.toLowerCase()))
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
      const savedTodo = await patchTodo(id, { status })
      setTodos((current) => current.map((item) => item.id === savedTodo.id ? savedTodo : item))
    })
  }

  const handleToggleDone = (todo) => {
    const status = todo.status === 'done' ? 'in_progress' : 'done'
    runAction('상태 변경', async () => {
      const savedTodo = await patchTodo(todo.id, { status })
      setTodos((current) => current.map((item) => item.id === savedTodo.id ? savedTodo : item))
    })
  }

  const handleSave = useCallback((card) => {
    if (!modal) return
    runAction(modal.mode === 'add' ? '추가' : '수정', async () => {
      let savedTodo
      if (modal.mode === 'add') {
        savedTodo = await createTodo(payloadOf({ ...emptyTodo(modal.status), ...card, status: modal.status }))
      } else {
        savedTodo = await updateTodo(modal.todo.id, payloadOf({ ...modal.todo, ...card }))
      }
      setTodos((current) => modal.mode === 'add'
        ? [...current, savedTodo]
        : current.map((todo) => todo.id === savedTodo.id ? savedTodo : todo))
      setModal(null)
    })
  }, [modal])

  const handleDelete = (todo) => {
    if (!confirm('정말 삭제할까요?')) return
    runAction('삭제', async () => {
      await deleteTodo(todo.id)
      setTodos((current) => current.filter((item) => item.id !== todo.id))
    })
  }

  const changeCalendarMonth = (offset) => {
    if (offset === 0) {
      setCalendarMonth(new Date())
      return
    }
    setCalendarMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1))
  }

  const addCalendarTodo = (date) => {
    const card = emptyTodo('planned')
    if (date) card.start_at = `${date}T09:00`
    setModal({ mode: 'add', status: 'planned', todo: card })
  }

  return (
    <div className="min-h-screen" style={{ background: '#f4f4f8' }}>
      <header
        className="sticky top-0 z-40 px-6 py-4 flex flex-wrap items-center justify-between gap-3"
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

        <div className="header-actions flex items-center gap-3">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs" style={{ color: '#8888a8' }}>⌕</span>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="할일 검색..."
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
          <div className="user-menu">
            <NotificationBell
              notifications={notifications}
              pendingCount={pendingTodos.length}
              now={now}
              onRead={handleReadNotification}
              onReadAll={handleReadAll}
              onOpenTodo={openTodoById}
              onOpenPending={() => setPanel('assignments')}
            />
            <span className="user-avatar" aria-hidden="true">{initials(me.display_name)}</span>
            <span className="text-xs font-medium" style={{ color: '#1a1a2e' }}>{me.display_name}</span>
            <button type="button" onClick={() => setPanel('friends')} className="user-menu-button">
              친구
              {friendRequests.received.length > 0 && (
                <span className="friend-badge" aria-label={`받은 친구 요청 ${friendRequests.received.length}개`}>{friendRequests.received.length}</span>
              )}
            </button>
            <button type="button" onClick={onLogout} className="user-menu-button">로그아웃</button>
            <button type="button" onClick={() => setPanel('delete-account')} className="user-menu-button is-danger">회원 탈퇴</button>
          </div>
        </div>
      </header>

      {error && <p className="px-6 pt-4 text-sm text-red-600">{error}</p>}

      <div className="split-layout">
        <div className="split-left">
          <nav className="view-sidebar" aria-label="보기 방식">
            {VIEWS.map((item) => (
              <button
                type="button"
                key={item.key}
                className={view === item.key ? 'is-active' : ''}
                aria-current={view === item.key ? 'page' : undefined}
                onClick={() => setView(item.key)}
              >
                <span className="view-sidebar-icon" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
            <div className="scope-filter" role="group" aria-label="할 일 범위">
              {SCOPES.map((item) => (
                <button
                  type="button"
                  key={item.key}
                  className={scope === item.key ? 'is-active' : ''}
                  aria-pressed={scope === item.key}
                  onClick={() => setScope(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </nav>

          {view === 'calendar' ? (
            <main className="calendar-main">
              <CalendarView
                todos={filtered}
                month={calendarMonth}
                onMonthChange={changeCalendarMonth}
                onEdit={(todo) => setModal({ mode: 'edit', status: todo.status, todo })}
                onAdd={addCalendarTodo}
              />
            </main>
          ) : (
            <main className="board-main">
              {STATUSES.map((col) => {
                const cards = filtered.filter((t) => t.status === col.key)
                const isTarget = dropTarget === col.key
                return (
                  <div
                    key={col.key}
                    className={`board-column flex flex-col rounded-2xl ${isTarget ? 'drop-target' : ''}`}
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
                          me={me}
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
                        할일 추가
                      </button>
                    </div>
                  </div>
                )
              })}
            </main>
          )}
        </div>

        <aside className="split-right">
          <ChecklistPanel
            todos={filtered}
            now={now}
            onToggle={handleToggleDone}
            onEdit={(todo) => setModal({ mode: 'edit', status: todo.status, todo })}
          />
        </aside>
      </div>

      {modal && (
        <CardModal
          title={modal.mode === 'add' ? '새 할일 추가' : '할일 편집'}
          card={modal.todo ?? emptyTodo(modal.status)}
          status={modal.status}
          friends={friends}
          me={me}
          onSave={handleSave}
          onClose={() => setModal(null)}
          onRespond={() => { setModal(null); setPanel('assignments') }}
        />
      )}

      {panel === 'friends' && (
        <FriendsModal friends={friends} requests={friendRequests} onChange={reloadFriends} onClose={() => setPanel(null)} />
      )}
      {panel === 'delete-account' && <DeleteAccountModal onDeleted={onLogout} onClose={() => setPanel(null)} />}
      {panel === 'assignments' && pendingTodos.length > 0 && (
        <AssignmentModal
          pending={pendingTodos}
          newIds={newAssignmentIds}
          todos={todos}
          me={me}
          onAccept={handleAccept}
          onReject={handleReject}
          onClose={() => setPanel(null)}
        />
      )}
    </div>
  )
}

export default function App() {
  const [me, setMe] = useState(null)
  const [checking, setChecking] = useState(() => Boolean(getToken()))

  const logout = useCallback(() => {
    setToken(null)
    setMe(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!getToken()) return
    getMe()
      .then(setMe)
      .catch(logout)
      .finally(() => setChecking(false))
  }, [logout])

  if (checking) return null
  if (!me) return <AuthScreen onLogin={(user) => { setChecking(false); setMe(user) }} />
  return <Board key={me.id} me={me} onLogout={logout} />
}
