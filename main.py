"""
╔══════════════════════════════════════════════════════════════════════╗
║  MAIN PIPELINE: Hệ thống Tự động Cào Web & Phân tích Video Đối thủ ║
║  Tác giả: Senior AI Data Engineer                                    ║
║  Portfolio: AI Data Specialist — Phân tích Video YouTube             ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  DATA PIPELINE:                                                      ║
║  ┌──────────┐   ┌──────────┐   ┌───────────┐   ┌──────────┐        ║
║  │ Scraping │ → │ Cleaning │ → │ Gemini AI │ → │ JSON DB  │        ║
║  │(Playwright│   │ (Regex)  │   │(Batching) │   │ (Output) │        ║
║  └──────────┘   └──────────┘   └───────────┘   └──────────┘        ║
║                                                                      ║
║  CÁCH CHẠY:                                                         ║
║  1. GEMINI_API_KEY=xxx python main.py                                ║
║  2. Custom URL: python main.py --url "https://youtube.com/watch?v="  ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝

YÊU CẦU CÀI ĐẶT:
  pip install playwright google-generativeai pandas
  playwright install chromium

YÊU CẦU BIẾN MÔI TRƯỜNG:
  export GEMINI_API_KEY=AIzaSy...
  (Lấy key tại: https://aistudio.google.com/apikey)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# ============================================================
# IMPORT CÁC MODULE ĐÃ TÁCH THEO CHUẨN SOLID
# ============================================================
# Single Responsibility: Mỗi module chỉ làm 1 việc
#   - scraper.py  = Cào dữ liệu từ YouTube (Playwright)
#   - cleaner.py  = Làm sạch data bằng Regex (miễn phí)
#   - analyzer.py = Gọi Gemini AI phân tích (tối ưu token)
from scraper import scrape_youtube_video
from cleaner import clean_metadata, clean_comments
from analyzer import analyze_with_nvidia

# ============================================================
# CẤU HÌNH LOGGING - Theo dõi từng bước pipeline
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# URL mặc định để phân tích (có thể override bằng --url)
DEFAULT_URL = "https://youtu.be/1VMNzrLmBhQ?si=_K-IEgRRK_50IvlU"
OUTPUT_FILE = "competitor_analysis.json"


# ============================================================
# HÀM CHÍNH: ORCHESTRATOR - Điều phối toàn bộ pipeline
# ============================================================

async def run_pipeline(url: str = None):
    """
    Hàm điều phối (Orchestrator) chạy toàn bộ Data Pipeline.

    KIẾN TRÚC SOLID:
    - Single Responsibility: Mỗi module chỉ làm 1 việc
    - Open/Closed: Có thể thêm module mới (vd: export_excel.py)
      mà không sửa code cũ
    - Dependency Inversion: Pipeline không phụ thuộc vào 1 AI provider
      (đã chuyển từ OpenAI → Gemini dễ dàng)

    LUỒNG XỬ LÝ:
    Step 1 → Scraping: Cào raw data từ YouTube (Playwright)
    Step 2 → Cleaning: Làm sạch data bằng Regex (MIỄN PHÍ)
    Step 3 → AI Analysis: SUPER BATCHING — 1 lần gọi Gemini duy nhất
    Step 4 → Output: Gộp kết quả → JSON file

    Args:
        url: URL YouTube cần phân tích (None = dùng DEFAULT_URL)

    Returns:
        dict chứa toàn bộ kết quả phân tích
    """
    target_url = url or DEFAULT_URL

    # ─────────────────────────────────────────────
    # KIỂM TRA GEMINI API KEY TRƯỚC KHI BẮT ĐẦU
    # ─────────────────────────────────────────────
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        logger.error("❌ Thiếu NVIDIA_API_KEY! Hãy set biến môi trường:")
        logger.error("   export NVIDIA_API_KEY=nvapi-...")
        logger.error("   hoặc: NVIDIA_API_KEY=nvapi-... python3 main.py")
        logger.error("   Lấy key miễn phí tại: https://build.nvidia.com")
        sys.exit(1)

    logger.info("=" * 65)
    logger.info("🚀 BẮT ĐẦU PIPELINE PHÂN TÍCH VIDEO ĐỐI THỦ")
    logger.info(f"🔗 URL: {target_url}")
    logger.info(f"🔑 API Key: {api_key[:8]}...{api_key[-4:]}")
    logger.info(f"🤖 AI Provider: NVIDIA NIM (Llama 3.1 405B)")
    logger.info("=" * 65)

    # ==========================================
    # STEP 1/4: WEB SCRAPING (Cào dữ liệu thực tế)
    # ==========================================
    logger.info("\n📌 STEP 1/4: Web Scraping (Playwright + Anti-Bot)...")
    logger.info("-" * 40)

    raw_data = await scrape_youtube_video(target_url)

    logger.info(f"  📊 Kết quả scraping:")
    logger.info(f"     - Title: {len(raw_data['title'])} ký tự")
    logger.info(f"     - Views: {raw_data['views']}")
    logger.info(f"     - Description: {len(raw_data['description'])} ký tự")
    logger.info(f"     - Comments: {len(raw_data['comments'])} bình luận")

    # ==========================================
    # STEP 2/4: DATA CLEANING (Làm sạch bằng Regex)
    # ==========================================
    logger.info("\n📌 STEP 2/4: Data Cleaning (Regex — miễn phí)...")
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
    # STEP 3/4: AI ANALYSIS (Gemini + SUPER BATCHING)
    # ==========================================
    logger.info("\n📌 STEP 3/4: AI Analysis (NVIDIA NIM — SUPER BATCHING)...")
    logger.info("-" * 40)

    # GỌI 1 LẦN DUY NHẤT cho cả metadata + comments
    # Đây là kỹ thuật SUPER BATCHING: tiết kiệm tối đa chi phí API
    ai_result = analyze_with_nvidia(
        metadata=clean_meta,
        comments=clean_cmts,
        api_key=api_key,
    )

    # Tách kết quả AI thành 2 phần
    video_analysis = ai_result.get("phan_tich_video", {})
    comments_analysis = ai_result.get("phan_tich_binh_luan", {})

    # ==========================================
    # STEP 4/4: OUTPUT — Xây dựng JSON lồng nhau (Nested JSON)
    # ==========================================
    logger.info("\n📌 STEP 4/4: Generating Output (Nested JSON)...")
    logger.info("-" * 40)

    # --- Xây dựng cấu trúc JSON nested chuyên nghiệp ---
    final_output = {
        # ── Thông tin pipeline ──
        "pipeline_info": {
            "project": "Hệ thống Phân tích Video Đối thủ (YouTube)",
            "version": "2.0.0",
            "author": "AI Data Engineer",
            "generated_at": datetime.now().isoformat(),
            "source_url": target_url,
            "ai_provider": "NVIDIA NIM (Llama 3.1 405B)",
            "pipeline_steps": [
                "Web Scraping (Playwright + Anti-Bot)",
                "Data Cleaning (Regex + Teencode Normalization)",
                "AI Analysis (Gemini + Super Batching)",
                "JSON Database Export",
            ],
        },
        # ── Phân tích metadata video ──
        "metadata": {
            "raw": {
                "title": raw_data["title"],
                "views": raw_data["views"],
                "description_length": len(raw_data["description"]),
            },
            "cleaned": clean_meta,
            "ai_analysis": video_analysis,
        },
        # ── Phân tích bình luận ──
        "comments": {
            "statistics": {
                "raw_count": len(raw_data["comments"]),
                "after_cleaning": len(clean_cmts),
                "removed": len(raw_data["comments"]) - len(clean_cmts),
                "api_calls_used": 1,  # SUPER BATCHING → chỉ 1 call!
                "api_calls_saved": max(len(clean_cmts), 1),
            },
            "cleaned_list": clean_cmts,
            "ai_analysis": comments_analysis.get("comments", []),
            "sentiment_summary": comments_analysis.get("tong_ket", {
                "tich_cuc": 0,
                "tieu_cuc": 0,
                "trung_lap": 0,
            }),
        },
        # ── Thông tin tối ưu chi phí ──
        "cost_optimization": {
            "technique": "Super Batching — gộp metadata + comments vào 1 API call duy nhất",
            "total_items_analyzed": len(clean_cmts) + 1,  # +1 cho metadata
            "api_calls_without_batching": len(clean_cmts) + 1,
            "api_calls_with_super_batching": 1,
            "savings_percentage": round(
                (1 - 1 / max(len(clean_cmts) + 1, 1)) * 100, 1
            ),
        },
    }

    # ─────────────────────────────────────────────
    # IN KẾT QUẢ RA CONSOLE
    # ─────────────────────────────────────────────
    output_json = json.dumps(final_output, ensure_ascii=False, indent=2)
    print("\n" + "=" * 65)
    print("📋 KẾT QUẢ PHÂN TÍCH HOÀN CHỈNH (Nested JSON)")
    print("=" * 65)
    print(output_json)

    # ─────────────────────────────────────────────
    # LƯU FILE JSON
    # ─────────────────────────────────────────────
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output_json)

    logger.info(f"\n💾 Đã lưu kết quả → {OUTPUT_FILE}")
    logger.info(f"📊 Tổng kết:")
    logger.info(f"   - Comments đã phân tích: {len(clean_cmts)}")
    logger.info(f"   - API calls sử dụng: 1 (Super Batching)")
    logger.info(f"   - Tiết kiệm: {final_output['cost_optimization']['savings_percentage']}% chi phí API")
    logger.info("✅ PIPELINE HOÀN THÀNH!")

    return final_output


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    # Hỗ trợ truyền URL qua command line: python main.py --url "https://..."
    url = None
    for i, arg in enumerate(sys.argv):
        if arg == "--url" and i + 1 < len(sys.argv):
            url = sys.argv[i + 1]

    asyncio.run(run_pipeline(url))
