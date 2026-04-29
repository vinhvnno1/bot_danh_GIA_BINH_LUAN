"""
╔══════════════════════════════════════════════════════════════════════╗
║  MAIN PIPELINE: Hệ thống Tự động Cào Web & Phân tích Video Đối thủ ║
║  Tác giả: Senior AI Data Engineer                                    ║
║  Portfolio: AI Data Specialist - Công ty Truyền thông YouTube        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  DATA PIPELINE:                                                      ║
║  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         ║
║  │ Scraping │ → │ Cleaning │ → │ AI API   │ → │ JSON DB  │         ║
║  │(Playwright│   │ (Regex)  │   │(Batching)│   │ (Output) │         ║
║  └──────────┘   └──────────┘   └──────────┘   └──────────┘         ║
║                                                                      ║
║  CÁCH CHẠY:                                                         ║
║  1. Có API key:  OPENAI_API_KEY=sk-xxx python main.py                ║
║  2. Demo mode:   python main.py  (dùng mock data + mock API)        ║
║  3. Custom URL:  python main.py --url "https://youtube.com/watch?v=" ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

YÊU CẦU CÀI ĐẶT:
  pip install playwright openai pandas
  playwright install chromium
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# Import các module đã tách theo chuẩn SOLID
from scraper import scrape_youtube_video
from cleaner import clean_metadata, clean_comments
from analyzer import analyze_metadata, analyze_comments_batch

# ============================================================
# CẤU HÌNH LOGGING - Theo dõi từng bước pipeline
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# URL mặc định để demo (video tiếng Việt phổ biến)
DEFAULT_URL = "https://youtube.com/shorts/rr2qgUTd4zo?si=_Muw5iZ0fs-o5ruI"
OUTPUT_FILE = "competitor_analysis_pipeline.json"


# ============================================================
# HÀM CHÍNH: ORCHESTRATOR - Điều phối toàn bộ pipeline
# ============================================================

async def run_pipeline(url: str = None):
    """
    Hàm điều phối (Orchestrator) chạy toàn bộ Data Pipeline.

    GIẢI THÍCH KIẾN TRÚC SOLID:
    - Single Responsibility: Mỗi module chỉ làm 1 việc
      (scraper.py = cào, cleaner.py = dọn, analyzer.py = phân tích)
    - Open/Closed: Có thể thêm module mới (vd: sentiment_deep.py)
      mà không sửa code cũ
    - Dependency Inversion: Pipeline không phụ thuộc vào 1 AI provider cụ thể
      (có thể đổi từ OpenAI sang Gemini dễ dàng)

    LUỒNG XỬ LÝ:
    Step 1 → Scraping: Cào raw data từ YouTube
    Step 2 → Cleaning: Làm sạch data bằng Regex (MIỄN PHÍ, không tốn API)
    Step 3 → AI Analysis: Gửi data sạch cho AI phân tích (TỐI ƯU token)
    Step 4 → Output: Gộp kết quả → JSON file
    """
    target_url = url or DEFAULT_URL
    logger.info("=" * 65)
    logger.info("🚀 BẮT ĐẦU PIPELINE PHÂN TÍCH VIDEO ĐỐI THỦ")
    logger.info(f"🔗 URL: {target_url}")
    logger.info("=" * 65)

    # ==========================================
    # STEP 1: WEB SCRAPING (Cào dữ liệu)
    # ==========================================
    logger.info("\n📌 STEP 1/4: Web Scraping...")
    logger.info("-" * 40)
    raw_data = await scrape_youtube_video(target_url)
    logger.info(f"  📊 Raw: {len(raw_data['comments'])} comments, "
                f"title={len(raw_data['title'])} chars")

    # ==========================================
    # STEP 2: DATA CLEANING (Làm sạch)
    # ==========================================
    logger.info("\n📌 STEP 2/4: Data Cleaning (Regex)...")
    logger.info("-" * 40)

    # 2a. Làm sạch metadata
    clean_meta = clean_metadata(
        title=raw_data["title"],
        views=raw_data["views"],
        description=raw_data["description"],
    )

    # 2b. Làm sạch comments
    clean_cmts = clean_comments(raw_data["comments"])

    # ==========================================
    # STEP 3: AI ANALYSIS (Prompt Engineering)
    # ==========================================
    logger.info("\n📌 STEP 3/4: AI Analysis (Prompt Engineering)...")
    logger.info("-" * 40)

    # Kiểm tra API key → quyết định dùng real API hay mock
    api_key = os.environ.get("OPENAI_API_KEY")
    client = None
    if api_key:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        logger.info("  🔑 Phát hiện OPENAI_API_KEY → dùng real API")
    else:
        logger.info("  ⚠️ Không có OPENAI_API_KEY → dùng mock response (demo mode)")

    # 3a. Phân tích metadata (1 API call)
    metadata_analysis = analyze_metadata(clean_meta, client)

    # 3b. Phân tích comments BATCHED (1 API call cho TẤT CẢ comments)
    comments_analysis = analyze_comments_batch(clean_cmts, client)

    # ==========================================
    # STEP 4: OUTPUT - Gộp thành JSON lồng nhau
    # ==========================================
    logger.info("\n📌 STEP 4/4: Generating Output...")
    logger.info("-" * 40)

    # --- Xây dựng cấu trúc JSON nested chuyên nghiệp ---
    final_output = {
        "pipeline_info": {
            "project": "Hệ thống Phân tích Video Đối thủ",
            "version": "1.0.0",
            "author": "AI Data Engineer",
            "generated_at": datetime.now().isoformat(),
            "source_url": target_url,
            "pipeline_steps": [
                "Web Scraping (Playwright)",
                "Data Cleaning (Regex)",
                "AI Analysis (GPT-4o-mini + Batching)",
                "JSON Database Export",
            ],
        },
        "metadata": {
            "raw": {
                "title": raw_data["title"],
                "views": raw_data["views"],
                "description_length": len(raw_data["description"]),
            },
            "cleaned": clean_meta,
            "ai_analysis": metadata_analysis,
        },
        "comments": {
            "statistics": {
                "raw_count": len(raw_data["comments"]),
                "after_cleaning": len(clean_cmts),
                "removed": len(raw_data["comments"]) - len(clean_cmts),
                "api_calls_used": 1,  # Nhờ BATCHING!
                "api_calls_saved": len(clean_cmts) - 1,  # So với gọi từng cái
            },
            "cleaned_list": clean_cmts,
            "ai_analysis": comments_analysis,
        },
        "cost_optimization": {
            "technique": "Batching - gộp tất cả comments vào 1 API call",
            "estimated_calls_without_batching": len(clean_cmts) + 1,
            "actual_calls_with_batching": 2,
            "savings_percentage": round(
                (1 - 2 / max(len(clean_cmts) + 1, 1)) * 100, 1
            ),
        },
    }

    # --- Sentiment summary ---
    if "comments" in comments_analysis:
        sentiments = [c.get("cam_xuc", "") for c in comments_analysis["comments"]]
        final_output["comments"]["sentiment_summary"] = {
            "tich_cuc": sentiments.count("Tích cực"),
            "tieu_cuc": sentiments.count("Tiêu cực"),
            "trung_lap": sentiments.count("Trung lập"),
        }

    # --- In ra console ---
    output_json = json.dumps(final_output, ensure_ascii=False, indent=2)
    print("\n" + "=" * 65)
    print("📋 KẾT QUẢ PHÂN TÍCH HOÀN CHỈNH (JSON)")
    print("=" * 65)
    print(output_json)

    # --- Lưu file ---
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output_json)
    logger.info(f"\n💾 Đã lưu kết quả → {OUTPUT_FILE}")
    logger.info("✅ PIPELINE HOÀN THÀNH!")

    return final_output


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    # Hỗ trợ truyền URL qua command line argument
    url = None
    for i, arg in enumerate(sys.argv):
        if arg == "--url" and i + 1 < len(sys.argv):
            url = sys.argv[i + 1]

    asyncio.run(run_pipeline(url))
