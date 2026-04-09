# 파이썬 3.10 슬림 이미지 사용 (가볍고 안정적)
FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 (필수 의존성만)
# curl_cffi 등을 위해 필요한 기본 빌드 툴만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 복사
COPY . .

# 스크립트 실행
CMD ["python", "main.py"]
