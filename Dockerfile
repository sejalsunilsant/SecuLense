FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY secu_lense ./secu_lense
COPY scripts ./scripts
COPY README.md ./
RUN pip install --no-cache-dir .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["uvicorn", "secu_lense.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
