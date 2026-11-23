# API image: FastAPI + bge-m3 + bge-reranker-v2-m3 on CPU, index baked in.
#   docker build -t au-visa-tax-rag-api .
#   docker run --env-file .env -p 8000:8000 au-visa-tax-rag-api
# data/index/ must exist (python -m src.retrieval.build_index) before building.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.hf \
    HF_HUB_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# CPU-only torch (the CUDA wheel would add ~5 GB).
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

# Models are downloaded at build time so the container starts without internet
# access to Hugging Face. Only the safetensors weights (no .bin / ONNX copies).
# WITH_RERANKER=0 leaves the reranker out (-2.2 GB image, ~-2.5 GB RAM); the
# hybrid_rerank mode then falls back to hybrid (used for the small AWS task).
ARG EMBEDDING_MODEL=BAAI/bge-m3
ARG RERANKER_MODEL=BAAI/bge-reranker-v2-m3
ARG WITH_RERANKER=1
RUN HF_HUB_OFFLINE=0 python -c "from huggingface_hub import snapshot_download as d; \
pats=['*.json','*.safetensors','sentencepiece.bpe.model','1_Pooling/*']; \
d('${EMBEDDING_MODEL}', allow_patterns=pats); \
'${WITH_RERANKER}' == '1' and d('${RERANKER_MODEL}', allow_patterns=pats)"
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL} RERANKER_MODEL=${RERANKER_MODEL} RERANK_ENABLED=${WITH_RERANKER}

COPY src/ src/
COPY data/index/ data/index/

# Non-root user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
