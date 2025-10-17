
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/ui/package.json apps/ui/pnpm-lock.yaml* apps/ui/tsconfig.json apps/ui/vite.config.ts ./
COPY apps/ui/tailwind.config.ts apps/ui/postcss.config.js ./
COPY apps/ui/index.html ./
COPY apps/ui/src ./src
RUN corepack enable && pnpm i && pnpm build

# Serve with nginx
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
