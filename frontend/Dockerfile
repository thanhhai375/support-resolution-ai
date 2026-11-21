# ==================================================
# SONGNHAT COPILOT — Frontend
# Stage 1 : node:20-alpine  → vite build
# Stage 2 : nginx:alpine    → serve on port 80
# ==================================================

# ---- Stage 1: Build ----
FROM node:20-alpine AS builder

WORKDIR /app

# Cache node_modules unless package*.json changes
COPY package.json package-lock.json ./
RUN npm ci

# Copy source & build
COPY . .
RUN npm run build

# ---- Stage 2: Serve ----
FROM nginx:alpine AS runner

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom nginx config: SPA fallback + API reverse-proxy to backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
