import unittest
from fastapi import HTTPException
from app.auth.rate_limit import LoginLimiter


class LoginRateLimitTest(unittest.TestCase):
    def test_accounts_are_throttled_independently_and_success_resets(self):
        limiter = LoginLimiter(limit=2)
        limiter.check("student1")
        limiter.check("student1")
        with self.assertRaises(HTTPException) as error:
            limiter.check("student1")
        self.assertEqual(error.exception.status_code, 429)
        limiter.check("student2")
        limiter.success("student1")
        limiter.check("student1")
