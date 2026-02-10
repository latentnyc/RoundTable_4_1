# Frontend Dockerfile (Local Verification)
# Stage 1: Build
FROM node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Build args can be passed here or env vars
ENV VITE_API_URL=http://localhost:8000
RUN npm run build

# Stage 2: Serve
FROM node:20-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist ./dist
CMD ["serve", "-s", "dist", "-l", "3000"]
