"""
Script test nhanh cho scraper.py
Chạy: python test_scraper.py
"""

import asyncio
import logging
import json
from scraper import scrape_youtube_video

# Bật logging để thấy tiến trình cào dữ liệu
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)

# ===== ĐỔI URL NÀY THÀNH VIDEO BẠN MUỐN TEST =====
TEST_URL = "https://youtu.be/1VMNzrLmBhQ?si=_K-IEgRRK_50IvlU"


async def main():
    print("=" * 60)
    print("🚀 BẮT ĐẦU TEST SCRAPER")
    print("=" * 60)

    result = await scrape_youtube_video(TEST_URL)

    # ─── In kết quả dễ đọc ───
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ CÀO DỮ LIỆU:")
    print("=" * 60)

    print(f"\n📌 Title: {result['title']}")
    print(f"👁️  Views: {result['views']}")
    print(f"📝 Description: {result['description'][:200]}...")

    print(f"\n💬 Comments ({len(result['comments'])} bình luận):")
    print("-" * 40)
    for i, comment in enumerate(result["comments"], 1):
        print(f"  {i}. {comment[:100]}")

    # ─── In JSON đầy đủ (để debug) ───
    print("\n" + "=" * 60)
    print("🔍 RAW JSON OUTPUT:")
    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
