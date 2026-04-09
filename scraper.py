from curl_cffi.requests import AsyncSession
import asyncio
from bs4 import BeautifulSoup
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://farside.co.uk/",
    "Upgrade-Insecure-Requests": "1"
}

# ─────────────────────────────────────────────────────────────────────────────
# ETF Flow  (Farside — 기존 유지)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_etf_flow(session, url):
    """Farside의 ETF 자금 유출입 데이터 스크래핑 (기존 로직 유지)"""
    MAX_RETRIES = 3
    html = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await session.get(url, headers=HEADERS, impersonate="chrome", timeout=20)
            if resp.status_code == 403:
                logger.warning(f"Cloudflare 403 on {url} (Attempt {attempt}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(5)
                    continue
                return None
            resp.raise_for_status()
            html = resp.text
            break
        except Exception as e:
            logger.error(f"Error fetching ETF flow from {url} (Attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2)
                continue
            return None

    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            thead = table.find("thead")
            if thead:
                header_row = thead.find("tr") or thead
                header_cells = header_row.find_all(["th", "td"])
            else:
                rows = table.find_all("tr")
                if not rows:
                    continue
                header_cells = rows[0].find_all(["th", "td"])

            headers = [th.get_text(strip=True) for th in header_cells]
            total_idx = next((i for i, h in enumerate(headers) if "Total" in h), -1)

            if total_idx != -1:
                tbody = table.find("tbody")
                rows = tbody.find_all("tr") if tbody else table.find_all("tr")

                for row in reversed(rows):
                    cells = row.find_all(["td", "th"])
                    if not cells or len(cells) <= total_idx:
                        continue

                    if "Total" in cells[total_idx].get_text(strip=True):
                        continue

                    date_text = cells[0].get_text(strip=True)
                    total = cells[total_idx].get_text(strip=True)

                    if date_text.lower() in ("total", "average", "maximum", "minimum", "mean", "median"):
                        continue

                    if total and total not in ("-", ""):
                        try:
                            if total.startswith("(") and total.endswith(")"):
                                total = "-" + total[1:-1]
                            flow_val = float(total.replace(",", ""))
                            return {"date": date_text, "flow_m": flow_val}
                        except ValueError:
                            continue

        logger.error(f"Total column or Valid Table not found on {url}")
        return None
    except Exception as e:
        logger.error(f"Error parsing ETF flow from {url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# OI 24h 변화율 — [교체] Binance 1h 구간 × 25포인트, sumOpenInterestValue(USD)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_binance_open_interest(session, symbol="BTCUSDT"):
    """
    OI 24h 변화율 (%) — Binance Futures 1h 히스토리 기반.
    sumOpenInterestValue(USD 환산) 사용으로 코인 수량 기준 오차 제거.
    """
    url = (
        f"https://fapi.binance.com/futures/data/openInterestHist"
        f"?symbol={symbol}&period=1h&limit=25"
    )
    MAX_RETRIES = 2
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await session.get(url, timeout=10)
            if resp.status_code == 429:
                logger.warning(f"Binance 429 Rate Limit on {symbol} OI (Attempt {attempt}/{MAX_RETRIES})")
                await asyncio.sleep(3)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            logger.error(f"[{symbol} OI] Fetch failed (Attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2)
                continue
            return None

    try:
        if data and len(data) >= 25:
            oi_24h_ago = float(data[0]["sumOpenInterestValue"])
            oi_now     = float(data[-1]["sumOpenInterestValue"])
            logger.debug(f"[{symbol} OI] 24h ago (USD): {oi_24h_ago:.4f}")
            logger.debug(f"[{symbol} OI] Current  (USD): {oi_now:.4f}")

            if oi_24h_ago > 0:
                change_pct = ((oi_now - oi_24h_ago) / oi_24h_ago) * 100
                return change_pct
            else:
                logger.error(f"[{symbol} OI] oi_24h_ago is zero or negative.")
        else:
            logger.error(f"[{symbol} OI] Insufficient data: {len(data) if data else 'None'}")
        return None
    except Exception as e:
        logger.error(f"[{symbol} OI] Processing failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 펀딩비 — [교체] Binance + OKX + Bybit 3개소 평균 집계
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_binance_funding_rate(session, symbol="BTCUSDT"):
    """펀딩비 집계 (%) — Binance + OKX + Bybit 평균."""
    base = symbol.replace("USDT", "")
    okx_symbol = f"{base}-USD-SWAP"

    binance_url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
    okx_url     = f"https://www.okx.com/api/v5/public/funding-rate?instId={okx_symbol}"
    bybit_url   = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"

    rates: list[float] = []
    
    # Binance
    try:
        resp = await session.get(binance_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rates.append(float(data.get("lastFundingRate", 0)) * 100)
    except Exception as e:
        logger.error(f"[Funding/{symbol}] Binance fetch failed: {e}")

    # OKX
    try:
        resp = await session.get(okx_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        okx_list = data.get("data", [])
        if okx_list:
            raw_str = okx_list[0].get("fundingRate")
            if raw_str:
                rates.append(float(raw_str) * 100)
    except Exception as e:
        logger.error(f"[Funding/{okx_symbol}] OKX fetch failed: {e}")

    # Bybit
    try:
        resp = await session.get(bybit_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ticker_list = data.get("result", {}).get("list", [])
        if ticker_list:
            raw_str = ticker_list[0].get("fundingRate")
            if raw_str:
                rates.append(float(raw_str) * 100)
    except Exception as e:
        logger.error(f"[Funding/{symbol}] Bybit fetch failed: {e}")

    if not rates:
        return None
    return sum(rates) / len(rates)


# ─────────────────────────────────────────────────────────────────────────────
# Coinbase Premium  (기존 유지)
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_coinbase_premium(session):
    binance_url  = "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT"
    coinbase_url = "https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/ticker"

    try:
        binance_resp, coinbase_resp = await asyncio.gather(
            session.get(binance_url, timeout=10),
            session.get(coinbase_url, headers={"cache-control": "no-cache"}, timeout=10)
        )
        binance_resp.raise_for_status()
        coinbase_resp.raise_for_status()

        binance_price = float(binance_resp.json().get("price", 0))
        coinbase_data = coinbase_resp.json()
        
        coinbase_price_str = None
        if "trades" in coinbase_data and len(coinbase_data["trades"]) > 0:
            coinbase_price_str = coinbase_data["trades"][0].get("price")

        if not coinbase_price_str:
            return None

        coinbase_price = float(coinbase_price_str)
        if binance_price > 0:
            return ((coinbase_price - binance_price) / binance_price) * 100
        return None
    except Exception as e:
        logger.error(f"Error fetching Coinbase Premium: {e}")
        return None

async def scrape_all_data():
    async with AsyncSession() as session:
        btc_url = "https://farside.co.uk/bitcoin-etf-flow-all-data/"
        eth_url = "https://farside.co.uk/ethereum-etf-flow-all-data/"

        tasks = {
            "btc_etf":       fetch_etf_flow(session, btc_url),
            "eth_etf":       fetch_etf_flow(session, eth_url),
            "btc_oi_change": fetch_binance_open_interest(session, "BTCUSDT"),
            "eth_oi_change": fetch_binance_open_interest(session, "ETHUSDT"),
            "btc_funding":   fetch_binance_funding_rate(session, "BTCUSDT"),
            "eth_funding":   fetch_binance_funding_rate(session, "ETHUSDT"),
            "cb_premium":    fetch_coinbase_premium(session),
        }

        results = await asyncio.gather(*tasks.values())
        return dict(zip(tasks.keys(), results))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    data = asyncio.run(scrape_all_data())
    print("\n--- Scraped Data ---")
    print(data)
