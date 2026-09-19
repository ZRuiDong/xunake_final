FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/node:24-alpine@sha256:d08b32cd3b4052dc3e5b67accb48a7dea41b8d1f3fdd4800491a1351131ff19a AS build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/nginx:stable-alpine@sha256:2b05ee6cfa2d752b8032c1b53597a4d1e800ba22ff8bfabc10da2c2427f4f6bd
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html
EXPOSE 80
