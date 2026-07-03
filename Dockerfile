# ── Stage 1: build the React frontend ──────────────────────────────
FROM node:20-slim AS webbuild
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ── Stage 2: Python runtime serving API + built UI ─────────────────
FROM python:3.11-slim
WORKDIR /app

# CPU-only PyTorch keeps the image small (no CUDA libraries)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements-space.txt .
RUN pip install --no-cache-dir -r requirements-space.txt

COPY . .
COPY --from=webbuild /web/dist ./web/dist

# Writable cache for the embedding model download at startup
ENV HF_HOME=/tmp/hf
EXPOSE 7860
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "7860"]
