🛠️ Crypto Evening Briefing Bot
인수인계 및 유지보수 가이드
📌 1. 프로젝트 개요

이 봇은 매일 21:00 KST 기준으로 실행되는
크립토 시장 자동 브리핑 시스템이다.

데이터 수집 → 분석 → 텔레그램 발행까지
완전 자동화된 배치 파이프라인 구조로 동작한다.

⚙️ 2. 시스템 구조
🔄 전체 파이프라인
scraper.py → generator.py → publisher.py
            ↓
          main.py (orchestrator)
실행 흐름
데이터 수집 (ETF / OI / 펀딩 / CB 프리미엄)
Claude 기반 브리핑 생성 (2단계 생성 + 교정)
텔레그램 채널 발행
📂 3. 파일 구조
파일명	역할
main.py	전체 실행 제어 + 재시도 로직
scraper.py	데이터 수집 (ETF / OI / 펀딩 / 프리미엄)
generator.py	Claude 기반 브리핑 생성
publisher.py	텔레그램 메시지 발송
DATA_SOURCES.md	데이터 검증 기준
.env	API 키 및 설정
session.session	텔레그램 인증 세션
📊 4. 데이터 구조
🌊 ETF
Farside 기준
최신 날짜 Total 값 사용
📉 OI (미결제약정)
Binance Futures API 사용
1h × 25개 데이터 기반 24h 변화율 계산
USD 기준 (sumOpenInterestValue)
💰 펀딩비
Binance + OKX + Bybit 평균값
일부 실패 시 가능한 소스만 평균
💎 코인베이스 프리미엄
(Coinbase 현물 - Binance 선물) / Binance 선물 * 100
🚀 5. 로컬 실행 방법
1. 의존성 설치
pip install -r requirements.txt
2. 환경 변수 설정 (.env)
ANTHROPIC_API_KEY=
API_ID=
API_HASH=
CHANNEL=
3. 데이터 테스트
python -c "import asyncio; from scraper import scrape_all_data; import json; print(json.dumps(asyncio.run(scrape_all_data()), indent=2))"
4. 전체 실행
python main.py
☁️ 6. GCP 운영 구조
Project ID: telegram-autobot-490509
Region: asia-northeast3
Job: evening-brief-job
Scheduler: evening-brief-scheduler
실행 구조
Cloud Scheduler → Cloud Run Job → Telegram
🧭 7. 운영 명령어
⏸️ 중지
gcloud scheduler jobs pause evening-brief-scheduler --location=asia-northeast3
▶️ 재개
gcloud scheduler jobs resume evening-brief-scheduler --location=asia-northeast3
🔁 수동 실행
gcloud run jobs execute evening-brief-job --region=asia-northeast3
🗑️ 리소스 삭제
gcloud scheduler jobs delete evening-brief-scheduler --location=asia-northeast3
gcloud run jobs delete evening-brief-job --region=asia-northeast3

⚠️ 프로젝트 삭제 아님 (리소스만 삭제됨)

🔄 8. 배포 방법
1. 이미지 빌드
gcloud builds submit --tag asia-northeast3-docker.pkg.dev/telegram-autobot-490509/telegram-bot-repo/evening-brief-job:latest .
2. Job 업데이트
gcloud run jobs update evening-brief-job \
--image asia-northeast3-docker.pkg.dev/telegram-autobot-490509/telegram-bot-repo/evening-brief-job:latest \
--region asia-northeast3
🚨 9. 장애 대응
텔레그램 메시지 안 올 때
Cloud Run Logs 확인
.env 확인
session.session 재로그인
데이터 오류
API 응답 변경 확인
scraper.py 수정
DATA_SOURCES.md 기준 검증
Claude 오류
API 키 확인
크레딧 확인
prompt 길이 확인
🧠 10. 핵심 수정 포인트
데이터 변경
scraper.py
문구/로직 변경
generator.py
발행 수정
publisher.py
✅ 11. 운영 체크리스트
 브리핑 정상 발행 확인
 숫자 이상 여부 확인
 텔레그램 포맷 깨짐 확인
 Claude 응답 이상 여부 확인
 로그 에러 여부 확인
🔐 12. 보안 주의
.env 절대 업로드 금지
session.session 외부 공유 금지
API 키는 인수인계 시 재발급 권장
📦 13. 인수인계 필수 항목
코드 전체
.env 항목 구조
GCP 프로젝트 정보
Artifact Registry 경로
텔레그램 채널 정보
DATA_SOURCES.md
이 문서
🔥 핵심 요약
이 시스템은:
- 21시 실행되는 배치형 크립토 리포트 봇
- Cloud Run Job 기반 서버리스 구조
- 데이터 → AI 분석 → 텔레그램 발행 파이프라인