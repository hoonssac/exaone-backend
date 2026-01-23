FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치 (Git LFS 포함)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    git \
    git-lfs \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Supertonic TTS 클론 및 모델 다운로드
RUN git clone https://github.com/supertone-inc/supertonic.git /app/supertonic && \
    cd /app/supertonic && \
    git clone https://huggingface.co/Supertone/supertonic-2 assets

# Supertonic 의존성 설치
RUN pip install --no-cache-dir -r /app/supertonic/py/requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8080

# 헬스체크
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# FastAPI 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
