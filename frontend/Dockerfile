# syntax=docker/dockerfile:1

FROM --platform=$BUILDPLATFORM node:24.15.0-slim AS build

RUN npm install --global npm@12.0.1

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG API_URL=/api
ARG FIREBASE_API_KEY
ARG FIREBASE_AUTH_DOMAIN
ARG FIREBASE_PROJECT_ID
ARG FIREBASE_APP_ID

RUN npm run build -- --configuration production


FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime

LABEL org.opencontainers.image.source="https://github.com/rstriletskyi-edu/kasyno-edu"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1



