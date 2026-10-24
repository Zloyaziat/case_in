# Статическая сборка SPA (ssr: false) + nginx: раздаёт build/client
# и проксирует /api на бэкенд (см. nginx.conf, BACKEND в compose-сети).
FROM node:24-alpine AS build-env
WORKDIR /app
COPY package.json bun.lock* package-lock.json* ./
RUN if [ -f bun.lock ]; then corepack enable && bun install --frozen-lockfile; \
    else npm ci; fi
COPY . .
RUN if [ -f bun.lock ]; then corepack enable && bun run build; \
    else npm run build; fi

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build-env /app/build/client /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
