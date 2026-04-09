# 📊 크립토 저녁 브리핑 데이터 검증 링크 (Validation Guide)

본 프로젝트의 `scraper.py`가 수집하는 데이터의 정확성을 수동으로 확인하고 싶을 때 아래 링크들을 참조하세요.

---

### 1. 🌊 BTC/ETH ETF 유출입 (Farside Investors)
봇은 이 사이트의 HTML 테이블에서 가장 최신 날짜의 'Total' 값을 추출합니다.
* **BTC ETF**: [https://farside.co.uk/bitcoin-etf-flow-all-data/](https://farside.co.uk/bitcoin-etf-flow-all-data/)
* **ETH ETF**: [https://farside.co.uk/ethereum-etf-flow-all-data/](https://farside.co.uk/ethereum-etf-flow-all-data/)
  - *확인 방법*: 테이블 맨 아래쪽 행의 `Total` 열 수치를 확인하세요. (단위: $m)

---

### 2. 📉 미결제약정(OI) 변동률 — **[교체됨] Binance 1h 구간 USD 기준**

> **기존**: `sumOpenInterest` (코인 수량 기준, `period=1d`, `limit=2`)  
> **신규**: `sumOpenInterestValue` (USD 환산 기준, `period=1h`, `limit=25`)

**변경 이유**: 코인 수량 기준은 BTC/ETH 가격 상승에 의해 수치가 왜곡될 수 있음.  
USD 기준으로 교체하고, 일별(1d) 버킷 대신 시간별(1h) 25개 포인트를 사용해  
data[0] (24h 전) vs data[24] (현재) 비교로 정확한 24h 윈도우 확보.

**API 엔드포인트**:
```
https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1h&limit=25
https://fapi.binance.com/futures/data/openInterestHist?symbol=ETHUSDT&period=1h&limit=25
```

**수동 확인**: [https://www.coinglass.com/pro/futures/OpenInterest](https://www.coinglass.com/pro/futures/OpenInterest)  
*확인 방법*: 'All Exchanges' 탭의 '24h Change %'를 확인하세요.

---

### 3. 💰 펀딩비 — **[교체됨] Binance + OKX + Bybit 3개소 평균 집계**

> **기존**: Binance `premiumIndex` 단일 소스  
> **신규**: Binance / OKX / Bybit 세 거래소 평균값 (가용 소스만 자동 집계)

**변경 이유**: 단일 거래소 기준은 일시적 스파이크/오류에 취약.  
3개소 병렬 수집 후 평균을 내어 편차를 줄인 집계값 사용.

**API 엔드포인트**:
| 거래소 | URL |
|--------|-----|
| Binance | `https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT` |
| OKX | `https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USD-SWAP` |
| Bybit | `https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT` |

**수동 확인**: [https://www.coinglass.com/FundingRate](https://www.coinglass.com/FundingRate)  
*확인 방법*: Binance / OKX / Bybit 각 행의 BTC, ETH 펀딩비를 평균 내어 비교하세요.

---

### 4. 💎 코인베이스 프리미엄 (Coinbase vs Binance) — 기존 유지
봇이 직접 계산하는 수치이며, 아래 지표 서비스와 추세가 일치하는지 비교할 수 있습니다.
* **CryptoQuant (Index)**: [https://cryptoquant.com/asset/btc/chart/market-indicator/coinbase-premium-index](https://cryptoquant.com/asset/btc/chart/market-indicator/coinbase-premium-index)
* **직접 계산법**:
  - 코인베이스 BTC 가격: [https://www.coinbase.com/price/bitcoin](https://www.coinbase.com/price/bitcoin)
  - 바이낸스 BTC 선물 가격: [https://www.binance.com/en/futures/BTCUSDT](https://www.binance.com/en/futures/BTCUSDT)
  - 계산식: `((코인베이스 가격 - 바이낸스 가격) / 바이낸스 가격) * 100`

---

### 🛠️ 데이터 즉시 확인 명령어 (터미널)
프로젝트 폴더에서 아래 명령어를 실행하면, 봇이 현재 인식하고 있는 가공 전 수치를 실시간으로 볼 수 있습니다.
```powershell
python -c "import asyncio; from scraper import scrape_all_data; import json; print(json.dumps(asyncio.run(scrape_all_data()), indent=2))"
```
