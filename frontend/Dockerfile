# =============================================================================
# NexusAI Frontend Production Dockerfile (Vite Build + Alpine Nginx)
# =============================================================================
FROM node:20-alpine as builder

WORKDIR /app

# Copy package definitions and install dependencies
COPY frontend/package.json /app/package.json
RUN npm install

# Copy source code and build production bundle
COPY frontend /app
RUN npm run build

# =============================================================================
# Production Nginx Serving Stage
# =============================================================================
FROM nginx:1.27-alpine as runner

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy built static SPA assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with reverse proxy & security headers
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

