import argparse
import os
from datetime import datetime, timedelta

from sqlalchemy import text

from app.auth.security import hash_password
from app.database import SessionLocal
from app.models.course import Course
from app.models.period import Period
from app.models.selection import Selection
from app.models.student import Student
from app.models.user import User
from app.utils.period import app_now


def parse_args():
    parser = argparse.ArgumentParser(
        description="Reset application tables and insert local test data."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Required confirmation for deleting all existing application data.",
    )
    return parser.parse_args()


def seed():
    if os.getenv("PRODUCTION", "false").lower() == "true":
        raise SystemExit("Refusing to reset a production database")
    args = parse_args()
    if not args.reset:
        raise SystemExit("Refusing to delete data without --reset")

    db = SessionLocal()
    now = app_now()

    try:
        db.execute(text(
            "TRUNCATE TABLE selections, courses, periods, students, users "
            "RESTART IDENTITY CASCADE"
        ))

        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="ADMIN",
        )
        db.add(admin)

        student_password = hash_password("123456")
        student_specs = [
            ("2026001", "张晨"),
            ("2026002", "李雨桐"),
            ("2026003", "王浩然"),
            ("2026004", "赵欣怡"),
            ("2026005", "陈子轩"),
            ("2026006", "刘思涵"),
            ("2026007", "杨博文"),
            ("2026008", "黄佳宁"),
            ("2026009", "周宇航"),
            ("2026010", "吴若曦"),
            ("2026011", "徐嘉乐"),
            ("2026012", "孙可心"),
        ]
        students = []

        for student_no, name in student_specs:
            user = User(
                username=student_no,
                password_hash=student_password,
                role="STUDENT",
            )
            db.add(user)
            db.flush()

            student = Student(
                user_id=user.id,
                student_no=student_no,
                name=name,
            )
            db.add(student)
            students.append(student)

        first_period = Period(
            name="第一轮选课（已结束）",
            start_time=now - timedelta(days=14),
            end_time=now - timedelta(days=7),
            status="CLOSED",
            finalized_time=now - timedelta(days=7),
        )
        current_period = Period(
            name="第二轮选课（进行中）",
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=7),
            status="ACTIVE",
        )
        db.add_all([first_period, current_period])
        db.flush()

        courses = [
            Course(
                name="创意绘画",
                description="色彩、构图与创意表达基础。",
                capacity=3,
                status="OPEN",
                period_id=first_period.id,
            ),
            Course(
                name="篮球基础",
                description="篮球基本技术和团队配合训练。",
                capacity=4,
                status="OPEN",
                period_id=first_period.id,
            ),
            Course(
                name="合唱艺术",
                description="声乐基础与多声部合唱实践。",
                capacity=4,
                status="OPEN",
                period_id=first_period.id,
            ),
            Course(
                name="摄影基础",
                description="构图、用光和校园摄影实践。",
                capacity=2,
                status="OPEN",
                period_id=current_period.id,
            ),
            Course(
                name="羽毛球",
                description="握拍、步法和基础对抗训练。",
                capacity=1,
                status="OPEN",
                period_id=current_period.id,
            ),
            Course(
                name="Python 创意编程",
                description="通过小游戏学习 Python 编程思维。",
                capacity=3,
                status="OPEN",
                period_id=current_period.id,
            ),
            Course(
                name="机器人入门",
                description="机器人结构、传感器与简单控制。",
                capacity=4,
                status="OPEN",
            ),
            Course(
                name="园艺实践",
                description="校园植物识别和基础栽培实践。",
                capacity=5,
                status="OPEN",
            ),
        ]
        db.add_all(courses)
        db.flush()

        selections = [
            Selection(
                student_id=students[0].id,
                course_id=courses[0].id,
                period_id=first_period.id,
                selected_time=now - timedelta(days=13),
                status="FINAL",
            ),
            Selection(
                student_id=students[1].id,
                course_id=courses[1].id,
                period_id=first_period.id,
                selected_time=now - timedelta(days=12),
                status="FINAL",
            ),
            # Three FINAL students in a capacity-two course exercise over-capacity UI.
            Selection(
                student_id=students[2].id,
                course_id=courses[3].id,
                period_id=current_period.id,
                selected_time=now - timedelta(hours=20),
                status="FINAL",
            ),
            Selection(
                student_id=students[3].id,
                course_id=courses[3].id,
                period_id=current_period.id,
                selected_time=now - timedelta(hours=19),
                status="FINAL",
            ),
            Selection(
                student_id=students[4].id,
                course_id=courses[3].id,
                period_id=current_period.id,
                selected_time=now - timedelta(hours=18),
                status="FINAL",
            ),
            Selection(
                student_id=students[5].id,
                course_id=courses[4].id,
                period_id=current_period.id,
                selected_time=now - timedelta(hours=10),
                status="SELECTED",
                queue_position=1,
            ),
            Selection(
                student_id=students[6].id,
                course_id=courses[4].id,
                period_id=current_period.id,
                selected_time=now - timedelta(hours=9),
                status="WAITING",
                queue_position=2,
            ),
        ]
        db.add_all(selections)
        db.commit()

        print("Test data seeded successfully")
        print("Admin: admin / admin123")
        print("Students: 2026001-2026012 / 123456")
        print("Active period: 第二轮选课（进行中）")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
