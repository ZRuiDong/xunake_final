FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12-slim@sha256:8d86cd5ae705baa369b0a74881b4811f28a60d2a2900d2a6221b65be7d481101
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
RUN pip install --index-url "$PIP_INDEX_URL" --no-cache-dir -r requirements.txt \
    && useradd --create-home app
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app init_db.py migrate.py create_admin.py ./
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--backlog", "2048", "--limit-concurrency", "500", "--no-proxy-headers"]
