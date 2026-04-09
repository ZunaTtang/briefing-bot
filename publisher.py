from telethon import TelegramClient
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

TELEGRAM_API_ID = os.getenv("API_ID")
TELEGRAM_API_HASH = os.getenv("API_HASH")
CHANNEL = os.getenv("CHANNEL")

async def post_to_telegram(message: str, image_path: str = None):
    """텔레그램 채널에 메시지 (및 이미지) 전송"""
    if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, CHANNEL]):
        logger.error("Telegram API credentials or CHANNEL env variables are missing!")
        return

    try:
        # If CHANNEL is numeric (e.g. -100123456), cast to int for telethon to recognize it as a Peer
        try:
            target_entity = int(CHANNEL)
        except ValueError:
            target_entity = CHANNEL

        async with TelegramClient("session", int(TELEGRAM_API_ID), TELEGRAM_API_HASH) as client:
            if image_path and os.path.exists(image_path):
                # parse_mode=None 으로 변경하여 뉴스 스니펫 등의 특수문자(_ 등)로 인한 파싱 에러 방지
                await client.send_file(target_entity, image_path, caption=message, parse_mode=None)
                logger.info("이미지와 함께 메시지 포스팅 성공")
            else:
                await client.send_message(target_entity, message, parse_mode=None)
                logger.info("메시지 포스팅 성공")
    except Exception as e:
        logger.error(f"Telegram posting failed: {e}")
        raise e  # main.py에서 재시도할 수 있도록 예외 상향 전달

