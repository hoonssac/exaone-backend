-- pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;

-- message_embeddings 테이블 생성
CREATE TABLE IF NOT EXISTS message_embeddings (
    id SERIAL PRIMARY KEY,
    thread_id INT NOT NULL REFERENCES chat_thread(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    embedding vector(384),  -- intfloat/multilingual-e5-small 임베딩 차원
    result_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성 (벡터 유사도 검색 최적화)
CREATE INDEX IF NOT EXISTS idx_message_embeddings_thread_id ON message_embeddings(thread_id);
CREATE INDEX IF NOT EXISTS idx_message_embeddings_embedding ON message_embeddings USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_message_embeddings_created_at ON message_embeddings(created_at DESC);

-- 테이블 설명
COMMENT ON TABLE message_embeddings IS 'RAG용 메시지 임베딩 저장소';
COMMENT ON COLUMN message_embeddings.embedding IS '문장 임베딩 벡터 (sentence-transformers)';
COMMENT ON COLUMN message_embeddings.result_data IS '쿼리 실행 결과 (JSON)';
