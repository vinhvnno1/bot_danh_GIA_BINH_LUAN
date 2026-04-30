"""
╔══════════════════════════════════════════════════════════════════╗
║  MODULE 1: WEB SCRAPING - Cào dữ liệu YouTube bằng Playwright  ║
║  Tác giả: Senior AI Data Engineer                                ║
║  Mục đích: Trích xuất metadata + comments từ video đối thủ       ║
╠══════════════════════════════════════════════════════════════════╣
║  CÔNG NGHỆ: Playwright (headless Chromium)                       ║
║  CHỐNG BOT: User-Agent rotation, random delay, human-like scroll ║
╚══════════════════════════════════════════════════════════════════╝

GIẢI THÍCH KỸ THUẬT:
- Playwright là thư viện tự động hóa trình duyệt (headless browser).
  Nó render JavaScript giống người dùng thật → vượt qua được các trang
  load động (SPA) mà requests/BeautifulSoup không làm được.
- YouTube load comments bằng AJAX khi cuộn trang → BẮT BUỘC phải dùng
  browser automation để scroll xuống rồi mới cào được.
"""

import asyncio
import random
import logging

logger = logging.getLogger(__name__)


# ============================================================
# PHẦN 1A: CẤU HÌNH CHỐNG PHÁT HIỆN BOT (Anti-Bot Config)
# ============================================================
# GIẢI THÍCH: YouTube và các trang lớn dùng nhiều kỹ thuật phát hiện bot:
#   1. Kiểm tra User-Agent → Ta giả lập UA của Chrome thật
#   2. Kiểm tra tốc độ request → Ta thêm delay ngẫu nhiên (human-like)
#   3. Kiểm tra hành vi chuột/cuộn → Ta mô phỏng scroll từ từ
#   4. Kiểm tra navigator.webdriver → Playwright tự xử lý flag này

# Danh sách User-Agent thật từ Chrome trên các OS khác nhau
# Mục đích: Xoay vòng (rotate) UA để tránh bị fingerprint
USER_AGENTS = [
    # Chrome 124 trên Windows 10
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 124 trên macOS Sonoma
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome 123 trên Ubuntu Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


async def _human_delay(min_s: float = 1.0, max_s: float = 3.0):
    """
    Delay ngẫu nhiên để giả lập hành vi con người.

    GIẢI THÍCH:
    Bot thường request liên tục không nghỉ → dễ bị phát hiện.
    Ta thêm khoảng nghỉ ngẫu nhiên giữa các thao tác.

    Args:
        min_s: Thời gian chờ tối thiểu (giây)
        max_s: Thời gian chờ tối đa (giây)
    """
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


async def _scroll_to_load_comments(page, max_scrolls: int = 8, target_comments: int = 20):
    """
    Cuộn trang từ từ để YouTube lazy-load phần comments.

    GIẢI THÍCH:
    - YouTube không load comments ngay khi mở trang
    - Phải scroll xuống phần comments section (~400-700px mỗi lần)
    - Mỗi lần scroll, chờ 2-4 giây để AJAX request hoàn thành
    - Kiểm tra số comments sau mỗi lần scroll → dừng sớm nếu đủ

    Args:
        page: Playwright page object
        max_scrolls: Số lần scroll tối đa (tránh vòng lặp vô hạn)
        target_comments: Số comments mục tiêu muốn load
    """
    for i in range(max_scrolls):
        # Cuộn xuống một khoảng ngẫu nhiên (giống người dùng thật)
        # Khoảng cách 400-700px mô phỏng cuộn chuột tự nhiên
        scroll_px = random.randint(400, 700)
        await page.evaluate(f"window.scrollBy(0, {scroll_px})")
        logger.info(f"  ↓ Scroll lần {i + 1}/{max_scrolls} ({scroll_px}px)")

        # Chờ ngẫu nhiên 2-4 giây để AJAX comments load xong
        await _human_delay(2.0, 4.0)

        # Kiểm tra số comments đã load → dừng sớm nếu đủ (tiết kiệm thời gian)
        count = await page.evaluate(
            "document.querySelectorAll('ytd-comment-thread-renderer #content-text').length"
        )
        if count >= target_comments:
            logger.info(f"  ✅ Đã đủ {count} comments, dừng scroll sớm")
            break


# ============================================================
# PHẦN 1B: HÀM CHÍNH - CÀO DỮ LIỆU YOUTUBE
# ============================================================

async def scrape_youtube_video(url: str) -> dict:
    """
    Hàm chính: Truy cập URL YouTube → trích xuất Metadata + Comments.

    LUỒNG XỬ LÝ:
    1. Khởi tạo browser Chromium ẩn (headless) với UA giả lập
    2. Mở trang video YouTube
    3. Chờ trang load xong → trích xuất metadata (title, views)
    4. Scroll xuống → chờ comments load → trích xuất comments
    5. Đóng browser → trả về dict chứa raw data

    Args:
        url: URL video YouTube cần phân tích
             (vd: https://youtube.com/watch?v=xxx hoặc youtube.com/shorts/xxx)

    Returns:
        dict với keys: 'title', 'views', 'description', 'comments'

    Raises:
        RuntimeError: Khi không cào được dữ liệu từ YouTube
    """
    from playwright.async_api import async_playwright

    # Cấu trúc kết quả trả về (khởi tạo giá trị mặc định)
    result = {"title": "", "views": "", "description": "", "comments": []}

    try:
        async with async_playwright() as pw:
            # ─────────────────────────────────────────────
            # BƯỚC 1: Khởi tạo browser với cấu hình chống bot
            # ─────────────────────────────────────────────
            # GIẢI THÍCH:
            #   - headless=True: Chạy ngầm không hiện cửa sổ (production mode)
            #   - user_agent: Giả lập Chrome thật, random từ danh sách
            #   - viewport: Set kích thước màn hình chuẩn Full HD
            #   - locale/timezone: Giả lập người dùng Việt Nam
            ua = random.choice(USER_AGENTS)
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=ua,
                viewport={"width": 1920, "height": 1080},
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
            )
            page = await context.new_page()
            logger.info(f"🌐 Mở trình duyệt | UA: {ua[:50]}...")

            # ─────────────────────────────────────────────
            # BƯỚC 2: Truy cập URL video
            # ─────────────────────────────────────────────
            # timeout=60s vì YouTube load khá nặng (nhiều JS bundle)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await _human_delay(3.0, 5.0)  # Chờ JS render xong
            logger.info(f"✅ Đã truy cập: {url}")

            # ─────────────────────────────────────────────
            # BƯỚC 3: Trích xuất METADATA
            # ─────────────────────────────────────────────
            # GIẢI THÍCH CSS SELECTORS:
            #   - h1.ytd-watch-metadata: Tiêu đề video trên trang watch
            #   - ytd-reel-video-renderer h2: Tiêu đề trên trang Shorts
            #   - #info-strings: Container chứa lượt xem + ngày đăng

            # 3a. Title — thử nhiều selector cho cả video thường và Shorts
            try:
                title_el = await page.wait_for_selector(
                    "h1.ytd-watch-metadata, "
                    "#title h1, "
                    "ytd-reel-video-renderer h2.ytd-reel-video-renderer",
                    timeout=15000,
                )
                result["title"] = (await title_el.inner_text()).strip()
            except Exception:
                # Fallback: Lấy từ thẻ <title> của trang HTML
                result["title"] = await page.title()
            logger.info(f"📌 Title: {result['title'][:60]}...")

            # 3b. Views / Lượt tương tác
            try:
                views_el = await page.query_selector(
                    "#info-strings yt-formatted-string, "
                    "ytd-video-view-count-renderer span, "
                    ".ytd-video-primary-info-renderer .view-count"
                )
                if views_el:
                    result["views"] = (await views_el.inner_text()).strip()
            except Exception:
                result["views"] = "N/A"

            # 3c. Description (cần click "Xem thêm" nếu bị ẩn)
            try:
                # Thử click nút mở rộng description
                expand_btn = await page.query_selector(
                    "tp-yt-paper-button#expand, "
                    "#description-inline-expander #expand"
                )
                if expand_btn:
                    await expand_btn.click()
                    await _human_delay(0.5, 1.0)

                desc_el = await page.query_selector(
                    "#description-inline-expander, "
                    "ytd-text-inline-expander .content"
                )
                if desc_el:
                    result["description"] = (await desc_el.inner_text()).strip()
            except Exception:
                result["description"] = ""

            # ─────────────────────────────────────────────
            # BƯỚC 4: Cuộn trang để load COMMENTS
            # ─────────────────────────────────────────────
            logger.info("📜 Bắt đầu scroll để load comments...")
            await _scroll_to_load_comments(page, max_scrolls=8, target_comments=20)

            # ─────────────────────────────────────────────
            # BƯỚC 5: Trích xuất COMMENTS
            # ─────────────────────────────────────────────
            # GIẢI THÍCH SELECTOR:
            #   - ytd-comment-thread-renderer: Container của 1 comment
            #   - #content-text: Phần text nội dung bình luận
            comment_elements = await page.query_selector_all(
                "ytd-comment-thread-renderer #content-text"
            )

            # Giới hạn 20 comments đầu tiên (theo yêu cầu)
            for el in comment_elements[:20]:
                text = (await el.inner_text()).strip()
                if text:  # Bỏ qua comments rỗng
                    result["comments"].append(text)

            logger.info(f"💬 Đã cào được {len(result['comments'])} comments thực tế")

            # Đóng browser giải phóng tài nguyên
            await browser.close()

    except Exception as e:
        logger.error(f"❌ Lỗi khi cào web: {e}")
        raise RuntimeError(f"Không thể cào dữ liệu từ YouTube: {e}") from e

    # Cảnh báo nếu không cào được comments (video tắt comments hoặc selector lỗi)
    if len(result["comments"]) < 1:
        logger.warning("⚠️ Không cào được comments — video có thể đã tắt bình luận")

    return result

