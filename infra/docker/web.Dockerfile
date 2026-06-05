FROM node:22-bookworm AS builder

WORKDIR /workspace
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/frontend-sdk/package.json packages/frontend-sdk/package.json

RUN pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages/frontend-sdk packages/frontend-sdk

RUN pnpm --filter @yggdrasil/web build

FROM node:22-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder /workspace/apps/web/.next/standalone ./
COPY --from=builder /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /workspace/apps/web/public ./apps/web/public

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
