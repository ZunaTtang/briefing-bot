import asyncio
import logging
import time
import os
from dotenv import load_dotenv
from scraper import scrape_all_data
from generator import generate_briefing
from publisher import post_to_telegram

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds

async def main():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"--- [Attempt {attempt}/{MAX_RETRIES}] Starting Evening Briefing Pipeline ---")
            
            # 1. 데이터 수집
            logger.info("Scraping data...")
            data = await scrape_all_data()
            logger.info(f"Scraped data summary: {data}")
            
            # 2. 메시지 및 인사이트 생성
            logger.info("Generating briefing message via Claude...")
            message = await generate_briefing(data)
            
            if not message or "오류가 발생했습니다" in message:
                raise ValueError(f"Briefing generation returned error: {message}")
            
            # 3. 텔레그램 발송
            logger.info("Posting to Telegram...")
            # 파이프라인에서 이미지 없이 텍스트만 전송 (Evening Briefing)
            await post_to_telegram(message)
            
            logger.info("Evening Briefing completed successfully!")
            break
            
        except Exception as e:
            logger.error(f"Error during attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Pipeline failed.")

if __name__ == "__main__":
    asyncio.run(main())
