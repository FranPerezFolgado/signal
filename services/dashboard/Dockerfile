FROM oven/bun:1

WORKDIR /app

COPY services/dashboard/package.json services/dashboard/bunfig.toml services/dashboard/bun.lock ./
RUN bun install --frozen-lockfile

COPY services/dashboard/ .

EXPOSE 5173

CMD ["bun", "run", "dev", "--host", "0.0.0.0"]
