FROM node:18-alpine

WORKDIR /app

# Копируем файлы зависимостей
COPY package*.json ./

# Устанавливаем ВСЕ зависимости (включая devDependencies)
RUN npm install

# Копируем конфигурационные файлы для Tailwind
COPY postcss.config.js ./
COPY tailwind.config.js ./

# Копируем остальные файлы
COPY . .

# Строим CSS с Tailwind
RUN npx tailwindcss -i ./src/index.css -o ./src/index.compiled.css

EXPOSE 3000

CMD ["npm", "start"]