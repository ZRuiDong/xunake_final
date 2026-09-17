import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';
import exec from 'k6/execution';

const fixtureFile = __ENV.ACCOUNTS_FILE || './accounts.local.json';
const accounts = new SharedArray('students', () => JSON.parse(open(fixtureFile)).accounts);
const courses = JSON.parse(open(fixtureFile)).course_ids;
const users = Number(__ENV.USERS || 1000);
if (users > accounts.length) throw new Error('Not enough distinct test accounts');
const base = __ENV.BASE_URL;
if (!base || __ENV.CONFIRM_LOADTEST !== 'true') throw new Error('Set BASE_URL to the isolated test deployment and CONFIRM_LOADTEST=true');

export const options = {
  scenarios: { burst: { executor: 'shared-iterations', vus: users, iterations: users, maxDuration: '2m' } },
  thresholds: {
    checks: ['rate>0.999'],
    'http_req_duration{operation:select}': ['p(95)<2000'],
    http_req_failed: ['rate<0.001'],
  },
};

function call(method, path, account, operation, expected = 200) {
  const response = http.request(method, `${base}${path}`, null, {
    headers: { Authorization: `Bearer ${account.token}` },
    timeout: '30s', tags: { operation },
    responseCallback: http.expectedStatuses(expected),
  });
  check(response, { [`${operation}: HTTP ${expected}`]: r => r.status === expected });
  return response;
}

export default function () {
  const index = exec.scenario.iterationInTest;
  const account = accounts[index];
  const offset = __ENV.MODE === 'hot' ? 0 : index % courses.length;
  const first = courses[offset];
  const second = courses[(offset + 1) % courses.length];
  const third = courses[(offset + 2) % courses.length];
  call('GET', '/student/courses', account, 'catalog');
  call('POST', `/student/select/${first}`, account, 'select');
  call('POST', `/student/select/${second}`, account, 'select');
  call('POST', `/student/select/${third}`, account, 'third-choice', 400);
  call('POST', `/student/select/${first}`, account, 'duplicate-select');
  call('DELETE', `/student/cancel/${second}`, account, 'cancel');
  call('DELETE', `/student/cancel/${second}`, account, 'duplicate-cancel');
  call('POST', `/student/select/${second}`, account, 'reselect');
  const profile = call('GET', '/student/profile', account, 'profile');
  check(profile, { 'student has exactly two choices': r => r.status === 200 && r.json('selections').length === 2 });
}
