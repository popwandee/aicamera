# Multi-stage build for production efficiency
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./
COPY ../shared/package*.json ../shared/
COPY ../../database/package*.json ../../database/

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .
COPY ../shared ../shared
COPY ../../database ../../database

# Build shared library first
WORKDIR /app/../shared
RUN npm run build

# Build database client
WORKDIR /app/../../database
RUN npm run generate

# Build application
WORKDIR /app
RUN npm run build

# Production stage
FROM node:20-alpine AS production

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create app user for security
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nestjs -u 1001

# Set working directory
WORKDIR /app

# Copy built application and dependencies
COPY --from=builder --chown=nestjs:nodejs /app/dist ./dist
COPY --from=builder --chown=nestjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nestjs:nodejs /app/package*.json ./

# Copy shared library
COPY --from=builder --chown=nestjs:nodejs /app/../shared/dist ../shared/dist
COPY --from=builder --chown=nestjs:nodejs /app/../shared/package*.json ../shared/

# Copy database client
COPY --from=builder --chown=nestjs:nodejs /app/../../database/generated ../../database/generated

# Switch to non-root user
USER nestjs

# Expose port
EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node dist/health-check.js || exit 1

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/main"]