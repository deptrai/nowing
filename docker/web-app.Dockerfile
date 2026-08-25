# Runtime Dockerfile for Web Builder standalone apps (Story 27.1c / AD-113)
#
# Build context MUST be the .next/standalone directory produced by BuilderService.
# BuilderService already ran npm install + next build, so this image only serves
# the pre-built standalone output. It avoids the double-build of the old
# multi-stage Dockerfile.
#
# Example build command (run from the project root):
#   docker build -f docker/web-app.Dockerfile \
#     /path/to/.local_object_store/web-app/{workspace_id}/{app_id}/.next/standalone \
#     -t nowing-web-app-{workspace_id}-{app_id}:{slug}
#
FROM node:20-alpine AS runner

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

WORKDIR /app

# The build context is the standalone directory, which already contains
# server.js, package.json, .next/, and the minimal node_modules set.
COPY --chown=node:node . /app

# Drop privileges before running the Next.js standalone server.
USER node

EXPOSE 3000

# Runtime healthcheck for container orchestrators (e.g. Docker Swarm, Caddy).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000', (r) => { process.exit(r.statusCode < 400 ? 0 : 1); }).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
