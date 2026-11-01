// fastapi-app/tests/load/todos_load.js
// 배포된 서버에 단계별 부하를 걸어 Grafana에서 지표 변화를 관찰하기 위한 k6 시나리오
//
// 실행 (k6를 설치하지 않고 Docker로):
//   docker run --rm --network host -v "$PWD/tests/load:/scripts" grafana/k6:1.3.0 run /scripts/todos_load.js
// 대상 서버 변경: -e BASE_URL=http://<서버>:5001
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');
const TITLE_PREFIX = 'k6-load';   // teardown 에서 이 접두사로 남은 데이터를 정리한다
const MAX_TODOS_PER_VU = 5;       // VU 하나가 들고 있는 항목 수 상한 → 전체 행 수가 무한히 늘지 않게
const JSON_HEADERS = { headers: { 'Content-Type': 'application/json' } };

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      // 3분마다 사용자 수를 올려 RPS가 더 오르지 않고 지연만 늘어나는 포화 지점을 찾는다
      stages: [
        { duration: '1m', target: 10 },   // 워밍업
        { duration: '3m', target: 10 },
        { duration: '30s', target: 50 },
        { duration: '3m', target: 50 },
        { duration: '30s', target: 100 },
        { duration: '3m', target: 100 },
        { duration: '30s', target: 200 },
        { duration: '3m', target: 200 },
        { duration: '1m', target: 0 },    // 쿨다운 (회복 양상 관찰)
      ],
      gracefulRampDown: '30s',
    },
  },
  teardownTimeout: '5m',   // 과부하 직후엔 서버가 밀린 요청을 처리하느라 정리 요청이 느릴 수 있다
  thresholds: {
    http_req_failed: ['rate<0.01'],                  // 에러율 1% 미만
    'http_req_duration{name:list}': ['p(95)<500'],   // 목록 조회 p95 500ms 미만
    'http_req_duration{name:write}': ['p(95)<800'],  // 생성/수정/삭제 p95 800ms 미만
  },
};

// VU마다 독립적으로 유지되는 상태 (k6는 VU별로 스크립트를 따로 실행함)
const myTodos = [];

function period() {
  const today = new Date().toISOString().slice(0, 10);
  return { start_at: `${today}T09:00`, end_at: `${today}T18:00` };
}

function listTodos() {
  const res = http.get(`${BASE_URL}/todos`, { tags: { name: 'list' } });
  check(res, { 'list 200': (r) => r.status === 200 });
}

function createTodo() {
  const payload = JSON.stringify({
    title: `${TITLE_PREFIX}-${__VU}-${__ITER}`,
    description: 'k6 부하 테스트 항목',
    ...period(),
  });
  const res = http.post(`${BASE_URL}/todos`, payload, { ...JSON_HEADERS, tags: { name: 'write', op: 'create' } });
  if (check(res, { 'create 201': (r) => r.status === 201 })) {
    myTodos.push(res.json('id'));
  }
}

function updateTodo() {
  const id = myTodos[Math.floor(Math.random() * myTodos.length)];
  const payload = JSON.stringify({
    title: `${TITLE_PREFIX}-${__VU}-updated`,
    description: '수정됨',
    status: 'in_progress',
    ...period(),
  });
  // URL에 id가 들어가도 name 태그로 묶어야 k6 지표가 id마다 쪼개지지 않는다
  const res = http.put(`${BASE_URL}/todos/${id}`, payload, { ...JSON_HEADERS, tags: { name: 'write', op: 'update' } });
  check(res, { 'update 200': (r) => r.status === 200 });
}

function deleteTodo() {
  const id = myTodos.shift();
  const res = http.del(`${BASE_URL}/todos/${id}`, null, { tags: { name: 'write', op: 'delete' } });
  check(res, { 'delete 204': (r) => r.status === 204 });
}

export function setup() {
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`${BASE_URL}/health 응답 ${res.status} — 서버 상태를 확인하세요`);
  }
}

// 요청 비율: 조회 70% / 생성 20% / 수정 5% / 삭제 5%
export default function () {
  const roll = Math.random();
  if (roll < 0.7 || (roll >= 0.9 && myTodos.length === 0)) {
    listTodos();
  } else if (roll < 0.9) {
    if (myTodos.length >= MAX_TODOS_PER_VU) deleteTodo();   // 상한에 닿으면 생성 대신 가장 오래된 항목 삭제
    else createTodo();
  } else if (roll < 0.95) {
    updateTodo();
  } else {
    deleteTodo();
  }
  sleep(Math.random() * 1 + 0.5);   // 사용자 생각 시간 0.5~1.5초
}

// 중간에 중단된 실행이 남긴 것까지 포함해 접두사로 만든 항목을 모두 지운다
export function teardown() {
  const res = http.get(`${BASE_URL}/todos`);
  if (res.status !== 200) return;
  const leftovers = res.json().filter((todo) => todo.title.startsWith(TITLE_PREFIX));
  for (const todo of leftovers) {
    http.del(`${BASE_URL}/todos/${todo.id}`);
  }
  console.log(`teardown: ${leftovers.length}개 정리`);
}
