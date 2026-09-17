# 生产部署与验收

## 部署

以下命令在 Linux 服务器的项目根目录执行。4 核 8 GB 可作为起始配置，
但是否支持千人同时操作必须用目标服务器压测确认。生产环境不使用 Vite 开发服务。

1. 复制根目录 `.env.example` 为 `.env`，设置 PostgreSQL、Redis 的真实密码。
   建议密码使用随机十六进制字符串，避免 URL 编码和 Compose 插值问题。
2. 复制 `backend/.env.example` 为 `backend/.env`，设置随机 JWT 密钥、初始学生密码。
   容器内数据库地址必须为 `postgres`，不能沿用本机/WSL IP：
   `DATABASE_URL=postgresql+psycopg2://course_admin:实际密码@postgres:5432/course_system`。
   数据库名、用户名与根目录 `.env` 一致。学生初始密码必须在首次登录时修改。
3. 首次空库部署：

```sh
docker compose -f docker-compose.yml -f deploy/compose.prod.yml up -d postgres redis
docker compose -f docker-compose.yml -f deploy/compose.prod.yml build backend web
docker compose -f docker-compose.yml -f deploy/compose.prod.yml run --rm backend python init_db.py
docker compose -f docker-compose.yml -f deploy/compose.prod.yml run --rm -it backend python create_admin.py
docker compose -f docker-compose.yml -f deploy/compose.prod.yml up -d backend web
```

管理员创建时交互输入至少 12 位的密码，没有默认 `admin123`，首次登录需要改密。
旧库不要运行初始化来代替升级，先备份，再按 [迁移说明](backend/migrations/README.md) 执行。
已建立版本记录的数据库只需要 `python migrate.py`，不要重跑 001—004。

默认 Web 仅绑定服务器 `127.0.0.1:8080`，应通过外层 HTTPS 反向代理访问。
调试可在根目录 `.env` 设置 `WEB_BIND_ADDRESS=0.0.0.0`，不要经公网 HTTP 传输真实账号密码。
生产启用 HTTPS、域名、防火墙，数据库/Redis 不开放公网，后端不发布宿主机端口。

内置 Nginx 提供静态文件、SPA 刷新回退和 `/api/` 前缀转发。
后端 4 workers，每个进程数据库最多 15 连接，总上限 60，为 PostgreSQL 管理、备份留空间。
不要直接将连接池/线程数增加到 1000；连接池耗尽、锁等待超时会返回 503，客户端需先查询实际结果。
登录失败按账号限流，生产用 Redis 跨进程共享，Redis 不可用时拒绝登录但不会取消学生已提交的选择。

## 升级与备份

备份包含学生隐私和密码哈希，文件不要提交 Git，应存储在受限目录并另存一份到服务器之外。
以下 PostgreSQL 备份格式是二进制，使用 Linux shell 重定向，不要使用旧版 PowerShell 重定向：

```sh
mkdir -p backups
chmod 700 backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/course.dump
chmod 600 backups/course.dump
```

文件名示例固定，实际备份应加日期避免覆盖。每天备份、选课开始前额外备份，并定期演练恢复。
恢复到新建的独立数据库验证，不要覆盖正在使用的数据库：

```sh
docker compose exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" course_restore'
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d course_restore' < backups/course.dump
```

删除学生/课程及关联选课记录会在同一事务写入 `audit_logs` 快照，不保留密码。
审计不是完整备份或一键撤销；误删后优先从隔离恢复库提取所需数据，不要直接整库回滚。
审计记录也包含个人信息，应限制数据库访问并制定保留期限。

## 回归与千人压测

```sh
cd backend
python -m unittest discover -s tests -v
```

设置 `TEST_DATABASE_URL` 后会额外运行 PostgreSQL 并发测试。
测试仅创建并清理随机 `test_selection_*` schema，需具备 CREATE SCHEMA 权限。
未设置该变量时并发测试明确跳过，SQLite 测试不能替代 PostgreSQL 的锁/触发器验证。

千人验收步骤：

1. 新建数据库，例如 `course_system_loadtest`，在**独立后端实例**中将 `DATABASE_URL`
   指向它。不得将生产后端临时切换为测试库。数据库名必须以 `_loadtest` 结尾。
2. 从 `backend` 工作目录运行 fixture 生成器，以便加载其 `.env`。
   该工具要求空库，拒绝覆盖已有数据/令牌文件。

```sh
cd backend
python ../loadtest/prepare.py --confirm-loadtest --students 1000 --output ../loadtest/accounts.local.json
```

3. 将 fixture 和 `selection.js` 放到另一台压测机，安装 k6。
   fixture 包含短期登录令牌，不得共享、提交；过期需要在新的空测试库重新准备。

```sh
cd loadtest
BASE_URL=https://测试域名/api CONFIRM_LOADTEST=true MODE=distributed k6 run selection.js
BASE_URL=https://测试域名/api CONFIRM_LOADTEST=true MODE=hot k6 run selection.js
```

**两种测试必须分别使用空库及新的 fixture**，重复使用原库会混合前次选择。
脚本每个测试学生使用独立账号，1000 并发开始，覆盖课程查询、选两门、拒绝第三门、
重复提交、退课重选及个人结果检查。它预生成令牌，**不测同时登录**；登录峰值需另测 bcrypt CPU 开销。

4. 从 `backend` 使用相同测试库配置执行 `python ../loadtest/verify.py`。
   应输出所有违规数为 0。建议验收指标：选课请求 P95 < 2 秒，意外 HTTP 失败率 < 0.1%，
   没有超过两门/异常超员/排名错误。容量指标不是现阶段性能承诺。
5. 同时观察 CPU、内存、数据库连接、锁等待、磁盘延迟和 503 数量。
   阶段结束和管理员修改容量的竞争已纳入 PostgreSQL 回归测试，正式验收还需在持续压测中验证。

## 业务边界

系统仍按单学期使用，每人最多两门有效选择（候补也占正在申请的名额），
未录取历史不占名额；阶段结束后学生不能自行修改最终名单，由管理员更正。
目前上课时间是自由文本，不自动判断两门课程的时间冲突。
跨学期复用和自动冲突检查需要明确学期/周次/节次规则后增加结构化数据，不能靠猜测文本解决。

配置参考：[Nginx 转发规则](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass)、
[Redis 原子脚本](https://redis.io/docs/latest/commands/eval/)。
