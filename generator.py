import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from anthropic import AsyncAnthropic
import pytz

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def deduplicate_news(articles):
    seen_titles, seen_domains = set(), {}
    result = []
    for a in articles:
        title_key = a.get("title", "")[:20].lower().strip()
        
        url = a.get("href", "") or a.get("url", "")
        domain = ""
        if url:
            try:
                domain = url.split("/")[2]
            except IndexError:
                pass
                
        if title_key in seen_titles: continue
        if domain and seen_domains.get(domain, 0) >= 2: continue
        
        seen_titles.add(title_key)
        if domain:
            seen_domains[domain] = seen_domains.get(domain, 0) + 1
            
        # 본문 전체 대신 제목 + 첫 200자만 전달 (토큰 절약)
        body = a.get("body", "")[:200]
        result.append({"title": a.get("title"), "snippet": body, "url": url})
        
    return result[:5]

async def perform_web_search(data):
    """지표 기반으로 쿼리를 생성하고 검색 수행"""
    kst = pytz.timezone("Asia/Seoul")
    today = datetime.now(kst).strftime("%Y-%m-%d")
    
    queries = [
        f"Bitcoin ETH crypto market news",
        f"BTC ETF fund flow",
        f"Federal Reserve inflation macro crypto"
    ]
    
    btc_etf = data.get("btc_etf", {}).get("flow_m", 0) if data.get("btc_etf") else 0
    funding = data.get("btc_funding", 0) if data.get("btc_funding") else 0
    oi_change = data.get("btc_oi_change", 0) if data.get("btc_oi_change") else 0
    
    if abs(btc_etf) > 200:
        queries.append(f"Bitcoin ETF large outflow reason")
    if funding < -0.05:
        queries.append(f"Bitcoin short squeeze liquidation")
    if abs(oi_change) > 10:
        queries.append(f"Bitcoin open interest liquidation cascade")
        
    all_articles = []
    
    try:
        # 동기 라이브러리인 DDGS를 asyncio 내에서 non-blocking으로 실행
        def _search():
            res = []
            with DDGS() as ddgs:
                for q in queries:
                    # 일자(주/월/일) 제한 등은 ddgs.news 또는 ddgs.text param으로 조절
                    search_res = ddgs.text(f"{q} {today}", max_results=3, safesearch="Off")
                    if search_res:
                        res.extend(search_res)
            return res
            
        articles = await asyncio.to_thread(_search)
        all_articles.extend(articles)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        
    return deduplicate_news(all_articles)

async def generate_briefing(data):
    client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY is not set.")
        return "ANTHROPIC_API_KEY missing."

    news = await perform_web_search(data)
    
    kst = pytz.timezone("Asia/Seoul")
    today_str = datetime.now(kst).strftime("%Y.%m.%d")
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][datetime.now(kst).weekday()]
    
    system_prompt = f"""
당신은 크립토 시장 전문 '트레이딩 의사결정 리포트'를 작성하는 최고 애널리스트 '크립토 갈매기'입니다.
제공되는 객관적 수치와 실시간 뉴스를 분석하여 독자가 "지금 롱/숏/관망 중 무엇을 할지 판단"할 수 있도록 명확하고 결단력 있는 브리핑을 작성합니다.

[절대 금지 사항]
- 출력 텍스트에 Markdown 서식 절대 사용 금지. *볼드*, **볼드**, _이탤릭_ 등 어떠한 마크다운 기호도 쓰지 마세요.
- 이모지와 •(불릿) 기호, →, ① ② ③ 등 일반 유니코드 기호만 허용됩니다.

[기본 작성 규칙]
1. 시간 기준: 본 브리핑은 21:00 KST 기준 작성됩니다. ETF는 전일(T-1) 흐름이며 파생(OI, 펀딩비)은 실시간 상태입니다. 따라서 "현재 상태"가 아닌 "다음 세션 기준 해석"으로 작성하세요.
2. 종결 어미: "~했습니다" 금지. 간결하고 단호하게 "~중", "~구간", "~가능성" 으로 끝내세요. 전체 통찰은 6문장 이내.
3. 과장 표현 극도로 제한 (매우 중요):
   - "기관 이탈"이라는 표현은 'ETF 유출'과 'OI 대폭 감소(≤ -5%)'가 동시에 발생할 때만 허용합니다.
   - 그 외에는 반드시 "약세 압력 증가", "포지션 축소", "수요 둔화 신호"로 표현하세요.
4. 디커플링 사용 제한: 가격 차이만으로 쓰지 마세요. 오직 ETF 흐름 방향과 OI 방향이 명확히 대비될 때만 사용하세요.
5. 데이터 본문 재방송 금지: 본문에서 수치를 주절주절 읽지 마세요.
6. 결론 강도 조절 (신호 일치도 기반):
   - 1개 지표만 특정 방향 시사 → "가능성 / 초입"
   - 2개 지표 일치 → "진행"
   - 3개 지표 일치 → "확정"

[지표별 해석 원칙]
- ETF: 기관 흐름 (방향성 판단의 핵심)
- OI (미결제약정): 포지션 변화 (시장 에너지 및 방향성 보강 핵심)
- 펀딩비: 보조 지표 (과열/쏠림 판단용). 펀딩비만으로 방향성을 단정짓지 마세요. ±0.003% 이내는 "중립"으로 간주합니다.
- 코인베이스 프리미엄(CB Premium): 커스텀 지표(Coinbase 현물 vs Binance 선물 차이)로, CryptoQuant 지표와 동일 지급 금지. 바이낸스 선물 베이시스 오차가 존재하므로 '보조 지표'로만 사용.
  * +0.05% 이상: 미국 현물 수요 유입 신호 (보조 확인 수준)
  * -0.05% 이하: 미국 현물 매도 우위 신호 (보조 확인 수준)
  * -0.05% ~ +0.05%: 중립 (방향성 해석 금지).
  * 단독으로 "기관 매수 강함", "미국 수요 확정" 등 강한 표현 절대 금지. 오직 ETF나 OI와 방향이 일치할 때만 보강용으로 씁니다.

[섹션별 작성 지침]
1. '다음 세션 관점' (한줄 요약): 단순 상황 설명 절대 금지. 반드시 "의미 + 방향성"을 포함하세요.
2. '현재 포지션 기준 해석' (4단계 구조 엄수):
   ① ETF (기관 흐름 분석)
   ② OI (포지션 변화 분석)
   ③ 펀딩비 및 CB 프리미엄 (과열 및 보조 수요 확인)
   ④ 최종 종합 파악 → 반드시 "롱 우위", "숏 우위", "관망 우위" 중 하나로 명시할 것.
3. '내일 볼 것': 단순 관찰 포인트 금지. 반드시 행동 조건(구체적 트리거)으로 작성. (예: "BTC ETF +20M 이상 시 롱 강화")
"""

    # Farside 데이터 없음 대응 (0.00일 때 순유출로 표시되는 문제 수정)
    btc_etf_data = data.get('btc_etf')
    eth_etf_data = data.get('eth_etf')
    
    if btc_etf_data and btc_etf_data.get('flow_m') is not None:
        v = btc_etf_data['flow_m']
        suffix = "순유입" if v > 0 else ("순유출" if v < 0 else "변동 없음")
        btc_etf_str = f"{v:+.2f}M ({suffix})"
    else:
        btc_etf_str = "데이터 없음"

    if eth_etf_data and eth_etf_data.get('flow_m') is not None:
        v = eth_etf_data['flow_m']
        suffix = "순유입" if v > 0 else ("순유출" if v < 0 else "변동 없음")
        eth_etf_str = f"{v:+.2f}M ({suffix})"
    else:
        eth_etf_str = "데이터 없음"
    
    btc_oi_str = f"{data.get('btc_oi_change', 0):+.2f}%" if data.get('btc_oi_change') is not None else "데이터 없음"
    eth_oi_str = f"{data.get('eth_oi_change', 0):+.2f}%" if data.get('eth_oi_change') is not None else "데이터 없음"
    
    btc_fund_str = f"{data.get('btc_funding', 0):+.4f}%" if data.get('btc_funding') is not None else "데이터 없음"
    eth_fund_str = f"{data.get('eth_funding', 0):+.4f}%" if data.get('eth_funding') is not None else "데이터 없음"
    
    cb_prem_str = f"{data.get('cb_premium', 0):+.4f}%" if data.get('cb_premium') is not None else "데이터 없음"

    user_prompt = f"""
[오늘의 요약 데이터]
📊 크립토 갈매기 브리핑 | {today_str} ({weekday_kr})

🌊 ETF 자금 흐름
• BTC ETF: {btc_etf_str}
• ETH ETF: {eth_etf_str}

📉 미결제약정 OI (24h)
• BTC: {btc_oi_str}
• ETH: {eth_oi_str}

💰 펀딩비
• BTC: {btc_fund_str}
• ETH: {eth_fund_str}

💎 코인베이스 프리미엄
• 현재: {cb_prem_str}

[오늘의 웹 검색 뉴스 스니펫 (전처리됨)]
{json.dumps(news, ensure_ascii=False, indent=2)}

위 데이터를 바탕으로 아래 포맷을 한 줄도 빠짐없이 유지하여 트레이딩 리포트를 작성해줘. 
(<데이터부분>은 위 내용을 그대로 복사붙여넣기 하고, 텍스트 파트만 완전히 새롭게 생성할 것)

<최종 출력 포맷>
📊 크립토 갈매기 브리핑 | {today_str} ({weekday_kr})

💬 다음 세션 관점
[의미와 방향성이 응축된 단일 핵심 문장]

🌊 ETF 자금 흐름
• BTC ETF: [데이터 그대로]
• ETH ETF: [데이터 그대로]

📉 미결제약정 OI (24h)
• BTC: [데이터 그대로]
• ETH: [데이터 그대로]

💰 펀딩비
• BTC: [데이터 그대로]
• ETH: [데이터 그대로]

💎 코인베이스 프리미엄
• 현재: [데이터 그대로]

📌 현재 포지션 기준 해석: [롱 우위 / 숏 우위 / 관망 우위 중 택1]
[① ETF 흐름 분석. ② OI 파생 분석. ③ 펀딩비 과열 분석. ④ 기사 이슈를 결합한 다음 세션 트레이딩 방향 통찰. (반드시 짧게 끊어치는 명사형 혹은 "~중", "~상태" 로 종결)]

📅 내일 볼 것
→ 강세: [구체적 수치 기반 행동 트리거. 예: 내일 BTC ETF +20M 이상 시 롱 강화]
→ 약세: [구체적 수치 기반 행동 트리거. 예: 펀딩비 -0.01% 돌파 시 투매 주의]
"""

    try:
        draft_response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        draft_message = draft_response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Error generating draft briefing via Claude: {e}")
        return f"초안 생성 중 오류가 발생했습니다: {e}"

    # 2단계: 유저가 제공한 '교정 전용 프롬프트'를 통한 2차 검수 (Two-pass)
    edit_system_prompt = """당신은 제공된 초안을 원본 데이터와 주어진 수정 규칙에 기반해 엄격하게 교정하고 출력 방식에 따라 '최종 결과물만' 반환하는 전문 교정 AI입니다.
절대 금지: 출력 텍스트에 Markdown 서식 (*볼드*, **볼드**, _이탤릭_ 등) 절대 사용 금지. 텔레그램에서 *텍스트* 형식은 볼드로 렌더링되므로, 별표(*)를 텍스트 강조 용도로 절대 사용하지 말 것. 이모지, •, →, ① ② ③ 같은 일반 유니코드 기호만 허용."""
    
    edit_user_prompt = f"""
✅ 수치 불일치 시 검증 API 기준으로 자동 교정하는 프롬프트

[기준 원시 데이터 (Source of Truth)]
- BTC ETF: {btc_etf_str} | ETH ETF: {eth_etf_str} (기준: Farside Investors 최신 Total)
- BTC OI: {btc_oi_str} | ETH OI: {eth_oi_str} (기준: Binance Futures 1d API)
- BTC 펀딩비: {btc_fund_str} | ETH 펀딩비: {eth_fund_str} (기준: Binance fapi/v1/premiumIndex)
- 코인베이스 프리미엄: {cb_prem_str} (기준: Coinbase 현물 - Binance 선물 직접 계산식)

아래 크립토 초안 브리핑을 수정할 때, 표시된 수치가 위 기준 원시 데이터(검증 API 원천값)와 다르면 반드시 원시 데이터 값으로 강제 교체한다.
Coinglass, CryptoQuant 등 시각화 사이트의 수치는 절대 최종 수치 기준으로 판단하지 마라. (오직 위 제공된 원시 데이터가 무조건 우선이다.)

1. 불일치 발생 시 처리 규칙
- 초안 수치와 원천값이 다른 경우 즉시 원천값으로 교체
- 부호(+/-)가 다르면 가장 우선적으로 수정

2. 계산 규칙 (이해용 백그라운드 지식)
- OI 변화율 = ((가장 최근 1d OI - 이전 1d OI) / 이전 1d OI) * 100
- Funding(%) = lastFundingRate * 100
- CB Premium(%) = ((Coinbase BTC-USD - Binance BTCUSDT Futures) / Binance BTCUSDT Futures) * 100

3. 검증 결과 반영 시 필수 제약
- ETF 수치가 맞으면 그대로 유지
- OI 또는 펀딩 시 이 수치가 다르면 반드시 제공된 기준 원시 데이터로 재기입
- CB 프리미엄은 '직접 제공된 계산값'만 쓰며 부차적 외부 지표인양 서술하지 말 것

4. 단어 및 해석 강도 의무 교정 (필수 반영) [반드시 수정할 항목]
- 수치가 바뀌면 해당 수치를 근거로 한 해석도 반드시 연쇄적으로 수정한다.
- “ETH 기관 이탈 확정” → 반드시 “ETH 약세 압력 진행 중”으로 교체 (초안에 해당 표현이 있으면 예외 없이 교체)
- “포지션 청산 가속 확정 구간” → 반드시 “포지션 축소 진행 구간”으로 교체 (초안에 해당 표현이 있으면 예외 없이 교체)
- “CME·ETF 오프라인 진입” → 반드시 “ETF 휴장 / CME holiday schedule 적용”으로 교체 (초안에 해당 표현이 있으면 예외 없이 교체)
- 공포탐욕지수(Fear & Greed Index, 공포지수, 공포/탐욕, 탐욕지수) 관련 문장·수치·서술이 초안에 있다면, 검증 불가 및 신뢰도 낮음으로 간주하여 해당 줄 자체를 브리핑에서 완전히 제거한다. (삭제 후 섹션 구조만 유지, 공백 줄 정리)
- “확정”, “이탈”, “붕괴”, “급락 확정”, “하락 확정” 등 강한 결론 표현은 기계적으로 제거 또는 완화한다.
  (예외: ETF 흐름 + OI 변화 + 펀딩비 세 지표가 모두 동일 방향을 가리킬 때만 “확정” 허용)
- 펀딩비가 ±0.003% 이내라면, 해당 항목의 해석을 즉시 “중립”으로 고친다.

5. 수정 범위 제한 (반드시 엄수)
- OI, 펀딩비, CB 프리미엄, ETF 수치 등 숫자(숫자값)는 기준 원시 데이터(API)에 맞추는 작업 외에는 절대 수정하거나 지어내지 않는다.
- 오직 문장과 표현(해석 강도, 단어 선택)만 최소 범위에서 수정한다.
- 기존 초안 포맷(섹션, 이모지, 줄바꿈, ①②③ 구조)과 구조는 그대로 유지한다.

6. 출력 방식 (반드시 준수)
- 수정에 대한 설명, 안내, 해설, 변경 이유 등 부가 설명은 절대 포함하지 말 것.
- 오직 "수정이 완료된 최종 브리핑" 본문만 출력할 것. 그 외 어떤 텍스트도 추가하지 말 것.

[크립토 브리핑 초안]
{draft_message}
"""

    try:
        final_response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            system=edit_system_prompt,
            messages=[
                {"role": "user", "content": edit_user_prompt}
            ]
        )
        return final_response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Error refining briefing via Claude: {e}")
        # 2차 수정 실패 시, 그나마 작성된 초안이라도 리턴
        return draft_message

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # 더미 데이터 테스팅
    dummy_data = {
        'btc_etf': {'date': '02 Apr', 'flow_m': -173.73}, 
        'eth_etf': {'date': '02 Apr', 'flow_m': -7.10}, 
        'btc_oi_change': -3.85, 
        'eth_oi_change': -9.84, 
        'btc_funding': -0.02, 
        'eth_funding': -0.01, 
        'cb_premium': 0.0562
    }
    
    logging.basicConfig(level=logging.INFO)
    message = asyncio.run(generate_briefing(dummy_data))
    print(message)
