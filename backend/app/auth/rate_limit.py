"""Per-account login throttling, shared across workers via Redis in production."""
import hashlib
import os
import time
from collections import OrderedDict
from threading import Lock

from fastapi import HTTPException
from redis import Redis, RedisError


class LoginLimiter:
    def __init__(self, client=None, limit=15, window=600):
        self.client = client
        self.limit = limit
        self.window = window
        self.attempts = OrderedDict()
        self.lock = Lock()

    def key(self, username):
        return "login:attempts:" + hashlib.sha256(username.encode("utf-8")).hexdigest()

    def check(self, username):
        key = self.key(username)
        if self.client is not None:
            try:
                count = self.client.eval("""
                    local n = redis.call('INCR', KEYS[1])
                    if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
                    return n
                """, 1, key, self.window)
            except RedisError as error:
                raise HTTPException(503, "login service temporarily unavailable") from error
        else:
            with self.lock:
                now = time.monotonic()
                count, expiry = self.attempts.pop(key, (0, now+self.window))
                if expiry <= now:
                    count, expiry = 0, now+self.window
                count += 1
                self.attempts[key] = (count, expiry)
                if len(self.attempts) > 10000:
                    self.attempts.popitem(last=False)
        if count > self.limit:
            raise HTTPException(429, "too many login attempts; try later",
                                headers={"Retry-After": str(self.window)})

    def success(self, username):
        if self.client is not None:
            try:
                self.client.delete(self.key(username))
            except RedisError as error:
                raise HTTPException(503, "login service temporarily unavailable") from error
        else:
            with self.lock:
                self.attempts.pop(self.key(username), None)


redis_host = os.getenv("LOGIN_REDIS_HOST")
if os.getenv("PRODUCTION", "false").lower() == "true" and not redis_host:
    raise RuntimeError("Production login throttling requires LOGIN_REDIS_HOST")
login_limiter = LoginLimiter(Redis(host=redis_host, password=os.getenv("REDIS_PASSWORD"),
    db=1, socket_connect_timeout=1, socket_timeout=1, max_connections=50) if redis_host else None)
