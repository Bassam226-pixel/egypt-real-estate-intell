FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-seed ChromaDB's default ONNX embedding model so first ingest doesn't
# block on a ~80MB runtime download.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warmup'])"

COPY . .

EXPOSE 8501

ENV PYTHONPATH=/
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

CMD ["streamlit", "run", "streamlit_app.py"]
