FROM oven/bun:1

WORKDIR /app

# Зависимости — отдельным слоем для кэша
COPY package.json bun.lock ./
RUN --mount=type=cache,target=/root/.bun/install/cache \
    bun install --frozen-lockfile

COPY . .

# Компилируем CSS
RUN bunx tailwindcss -i src/style.css -o public/style.css --minify

ENV PORT=3000

CMD ["bun", "run", "src/index.ts"]
