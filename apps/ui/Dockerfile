
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/ui/package.json apps/ui/package-lock.json* apps/ui/tsconfig.json apps/ui/vite.config.ts ./
COPY apps/ui/tailwind.config.ts apps/ui/postcss.config.js ./
COPY apps/ui/index.html ./
COPY apps/ui/src ./src
RUN npm ci && npm run build

# Serve with nginx
FROM nginx:1.27-alpine
RUN apk add --no-cache curl
COPY --from=build /app/dist /usr/share/nginx/html
