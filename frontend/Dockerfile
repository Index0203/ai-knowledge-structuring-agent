FROM node:20-alpine

WORKDIR /app
RUN corepack enable
COPY package.json ./
RUN pnpm install --no-frozen-lockfile
COPY . .

EXPOSE 3000
CMD ["pnpm", "run", "dev", "--hostname", "0.0.0.0"]
