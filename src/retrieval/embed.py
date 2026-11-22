"""bge-m3 embedding model (dense vectors, normalised for cosine / inner product)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .config import EMBEDDING_MODEL

MAX_SEQ_LENGTH = 1024  # chunks are <= ~600 tokens; caps memory on a 4 GB GPU


@lru_cache(maxsize=1)
def get_model():
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    kwargs = {"torch_dtype": torch.float16} if device == "cuda" else {}
    model = SentenceTransformer(EMBEDDING_MODEL, device=device, model_kwargs=kwargs)
    model.max_seq_length = MAX_SEQ_LENGTH
    return model


def encode(texts: list[str], batch_size: int = 16, progress: bool = False) -> np.ndarray:
    vecs = get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=progress,
    )
    return vecs.astype("float32")
