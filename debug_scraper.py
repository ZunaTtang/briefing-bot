"""
debug_scraper.py -- 4월 6일 기준 데이터 정확성 교차 검증 스크립트
실행: python debug_scraper.py
"""
import asyncio
import json
import logging
import sys

# Windows cp949 인코딩 문제 해결
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime, timezone, timedelta
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.DEBUG, format="%(message)s")
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)

SEPARATOR = "=" * 65


# ─── 1. Farside ETF ─────────────────────────────────────────────
async def debug_farside(session, label, url):
    print(f"\n{SEPARATOR}")
    print(f"[{label}] Farside 원문 테이블 — 최근 5행")
    print(SEPARATOR)
    try:
        resp = await session.get(url, impersonate="chrome", timeout=20)
        print(f"  HTTP {resp.status_code}")
        if resp.status_code != 200:
            print("  ❌ Farside 접근 실패")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            print("  ❌ 테이블 없음 — Cloudflare 차단 가능성")
            return

        for table in tables:
            thead = table.find("thead")
            if thead:
                header_cells = (thead.find("tr") or thead).find_all(["th", "td"])
            else:
                rows = table.find_all("tr")
                header_cells = rows[0].find_all(["th", "td"]) if rows else []

            headers = [h.get_text(strip=True) for h in header_cells]
            if "Total" not in " ".join(headers):
                continue

            total_idx = next((i for i, h in enumerate(headers) if "Total" in h), -1)
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else table.find_all("tr")

            print(f"  헤더: {headers[:4]} ... [{headers[total_idx]}]")
            print(f"  총 데이터 행 수: {len(rows)}")
            print()

            valid_rows = []
            for row in reversed(rows):
                cells = row.find_all(["td", "th"])
                if not cells or len(cells) <= total_idx:
                    continue
                date = cells[0].get_text(strip=True)
                total = cells[total_idx].get_text(strip=True)
                if date.lower() in ("total", "average", "maximum", "minimum", "mean", "median"):
                    continue
                if total and total not in ("-", ""):
                    valid_rows.append((date, total))
                if len(valid_rows) >= 5:
                    break

            for date, total in valid_rows:
                # 음수 포맷: (123.4) → -123.4
                val_str = total
                if val_str.startswith("(") and val_str.endswith(")"):
                    val_str = "-" + val_str[1:-1]
                try:
                    val = float(val_str.replace(",", ""))
                    arrow = "📈" if val > 0 else ("📉" if val < 0 else "➡️")
                    print(f"  {arrow}  {date:20s} | 총 유출입 = {val:+.2f}M USD")
                except ValueError:
                    print(f"  ⚠️  {date:20s} | 파싱 불가: {total}")

            print()
            # 가장 최신 날짜 확인
            if valid_rows:
                latest_date = valid_rows[0][0]
                print(f"  ✅ 스크레이퍼가 사용하는 최신 날짜: {latest_date}")
                # 4월 6일 오전에는 금요일(Apr 3) 데이터가 최신이어야 정상
                if "03 Apr" in latest_date or "3 Apr" in latest_date:
                    print("  ✅ 정상: 오늘(월요일) 기준 최신 영업일 데이터(April 3)")
                elif "02 Apr" in latest_date or "2 Apr" in latest_date:
                    print("  ⚠️  April 2 데이터: Farside가 아직 April 3 업데이트 안 됐을 수 있음")
                else:
                    print(f"  ℹ️  최신 날짜={latest_date} — 수동 확인 권장")
            break

    except Exception as e:
        print(f"  ❌ 오류: {e}")


# ─── 2. Binance OI ─────────────────────────────────────────────
async def debug_oi(session, symbol):
    print(f"\n{SEPARATOR}")
    print(f"[OI] Binance {symbol} — 24h 변화율 검증")
    print(SEPARATOR)

    url = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=25"
    try:
        resp = await session.get(url, timeout=10)
        print(f"  HTTP {resp.status_code}")
        data = resp.json()

        if not data or len(data) < 25:
            print(f"  ❌ 데이터 부족: {len(data) if data else 0}개 (25개 필요)")
            return

        first = data[0]
        last  = data[-1]

        ts_24h_ago = datetime.fromtimestamp(first["timestamp"] / 1000, tz=KST)
        ts_now     = datetime.fromtimestamp(last["timestamp"]  / 1000, tz=KST)
        oi_24h_ago = float(first["sumOpenInterestValue"])
        oi_now     = float(last["sumOpenInterestValue"])
        change_pct = ((oi_now - oi_24h_ago) / oi_24h_ago) * 100

        print(f"  기준 시각 (24h 전): {ts_24h_ago.strftime('%Y-%m-%d %H:%M KST')}")
        print(f"  기준 시각 (현재):   {ts_now.strftime('%Y-%m-%d %H:%M KST')}")
        print(f"  실제 시간차:        {(ts_now - ts_24h_ago).total_seconds()/3600:.1f}시간")
        print(f"  OI 24h 전 (USD):   {oi_24h_ago:,.0f}")
        print(f"  OI 현재  (USD):    {oi_now:,.0f}")
        arrow = "📈" if change_pct > 0 else "📉"
        print(f"  {arrow} 24h 변화율: {change_pct:+.4f}%")
        print()

        # 실제 시간차가 23~25시간 범위인지 확인
        hours_diff = (ts_now - ts_24h_ago).total_seconds() / 3600
        if 22 <= hours_diff <= 26:
            print(f"  ✅ 정상: 24h 윈도우 정확 ({hours_diff:.1f}h)")
        else:
            print(f"  ⚠️  비정상 윈도우: {hours_diff:.1f}h (기대값: ~24h)")

    except Exception as e:
        print(f"  ❌ 오류: {e}")


# ─── 3. Funding Rate ────────────────────────────────────────────
async def debug_funding(session, symbol):
    base = symbol.replace("USDT", "")
    okx_sym = f"{base}-USD-SWAP"

    print(f"\n{SEPARATOR}")
    print(f"[펀딩비] {symbol} — Binance / OKX / Bybit 교차 검증")
    print(SEPARATOR)

    sources = {}

    # Binance
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        resp = await session.get(url, timeout=10)
        data = resp.json()
        raw = float(data.get("lastFundingRate", 0))
        pct = raw * 100
        sources["Binance"] = pct
        print(f"  Binance: lastFundingRate={raw} → {pct:+.6f}%")
    except Exception as e:
        print(f"  ❌ Binance 오류: {e}")

    # OKX
    try:
        url = f"https://www.okx.com/api/v5/public/funding-rate?instId={okx_sym}"
        resp = await session.get(url, timeout=10)
        data = resp.json().get("data", [{}])[0]
        raw = float(data.get("fundingRate", 0))
        pct = raw * 100
        sources["OKX"] = pct
        settle_ts = int(data.get("fundingTime", 0))
        settle_dt = datetime.fromtimestamp(settle_ts / 1000, tz=KST).strftime("%H:%M KST") if settle_ts else "?"
        print(f"  OKX:     fundingRate={raw} → {pct:+.6f}% (정산예정: {settle_dt})")
    except Exception as e:
        print(f"  ❌ OKX 오류: {e}")

    # Bybit
    try:
        url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
        resp = await session.get(url, timeout=10)
        ticker = resp.json().get("result", {}).get("list", [{}])[0]
        raw = float(ticker.get("fundingRate", 0))
        pct = raw * 100
        sources["Bybit"] = pct
        next_ts = int(ticker.get("nextFundingTime", 0))
        next_dt = datetime.fromtimestamp(next_ts / 1000, tz=KST).strftime("%H:%M KST") if next_ts else "?"
        print(f"  Bybit:   fundingRate={raw} → {pct:+.6f}% (다음정산: {next_dt})")
    except Exception as e:
        print(f"  ❌ Bybit 오류: {e}")

    if sources:
        avg = sum(sources.values()) / len(sources)
        print()
        print(f"  📊 집계 {list(sources.keys())} → 평균 {avg:+.6f}%")
        if abs(avg) <= 0.003:
            print("  ✅ 중립 구간 (±0.003% 이내)")
        elif avg > 0:
            print("  🐂 롱 우위 펀딩비 (매수 포지션 과열)")
        else:
            print("  🐻 숏 우위 펀딩비 (매도 포지션 과열)")


# ─── 4. Coinbase Premium ────────────────────────────────────────
async def debug_cb_premium(session):
    print(f"\n{SEPARATOR}")
    print("[코인베이스 프리미엄] Coinbase 현물 vs Binance 선물")
    print(SEPARATOR)

    try:
        b_url = "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT"
        c_url = "https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/ticker"

        b_resp, c_resp = await asyncio.gather(
            session.get(b_url, timeout=10),
            session.get(c_url, headers={"cache-control": "no-cache"}, timeout=10)
        )

        binance_price = float(b_resp.json()["price"])
        c_data = c_resp.json()

        coinbase_price = None
        if "trades" in c_data and c_data["trades"]:
            coinbase_price = float(c_data["trades"][0]["price"])

        if coinbase_price is None:
            print("  ❌ Coinbase 가격 파싱 실패")
            print(f"  Coinbase 응답 키: {list(c_data.keys())}")
            return

        premium = ((coinbase_price - binance_price) / binance_price) * 100
        arrow = "📈" if premium > 0.05 else ("📉" if premium < -0.05 else "➡️")

        print(f"  Binance 선물:    ${binance_price:,.2f}")
        print(f"  Coinbase 현물:   ${coinbase_price:,.2f}")
        print(f"  {arrow} CB 프리미엄:   {premium:+.4f}%")
        print()
        if premium > 0.05:
            print("  ✅ +0.05% 초과: 미국 현물 수요 유입 신호")
        elif premium < -0.05:
            print("  ✅ -0.05% 미만: 미국 현물 매도 우위 신호")
        else:
            print("  ✅ 중립 구간 (-0.05% ~ +0.05%): 방향성 해석 금지")

    except Exception as e:
        print(f"  ❌ 오류: {e}")


# ─── 메인 ───────────────────────────────────────────────────────
async def main():
    print(f"\n{'#'*65}")
    print(f"# 크립토 갈매기 데이터 교차 검증 - {NOW_KST.strftime('%Y-%m-%d %H:%M KST')} #")
    print(f"{'#'*65}")

    async with AsyncSession() as session:
        await asyncio.gather(
            debug_farside(session, "BTC ETF", "https://farside.co.uk/bitcoin-etf-flow-all-data/"),
            debug_farside(session, "ETH ETF", "https://farside.co.uk/ethereum-etf-flow-all-data/"),
            debug_oi(session, "BTCUSDT"),
            debug_oi(session, "ETHUSDT"),
            debug_funding(session, "BTCUSDT"),
            debug_funding(session, "ETHUSDT"),
            debug_cb_premium(session),
        )

    print(f"\n{SEPARATOR}")
    print("검증 완료")
    print(SEPARATOR)


if __name__ == "__main__":
    asyncio.run(main())
