FROM oven/bun:1

WORKDIR /app

# Зависимости — отдельным слоем для кэша
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

# Компилируем CSS
RUN bunx tailwindcss -i src/style.css -o public/style.css --minify

ENV PORT=3000

CMD ["bun", "run", "src/index.ts"]
