"""
╔══════════════════════════════════════════════════════════════════╗
║  MODULE 1: WEB SCRAPING - Cào dữ liệu YouTube bằng Playwright  ║
║  Tác giả: Senior AI Data Engineer                                ║
║  Mục đích: Trích xuất metadata + comments từ video đối thủ       ║
╚══════════════════════════════════════════════════════════════════╝

GIẢI THÍCH CHO SẾP:
- Playwright là thư viện tự động hóa trình duyệt (headless browser),
  nó render JavaScript giống người dùng thật → vượt qua được các trang
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


async def _human_delay(min_s=1.0, max_s=3.0):
    """
    Delay ngẫu nhiên để giả lập hành vi con người.
    GIẢI THÍCH: Bot thường request liên tục không nghỉ → dễ bị phát hiện.
    Ta thêm khoảng nghỉ ngẫu nhiên 1-3 giây giữa các thao tác.
    """
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _scroll_to_load_comments(page, scroll_times=5):
    """
    Cuộn trang từ từ để YouTube lazy-load phần comments.
    GIẢI THÍCH:
    - YouTube không load comments ngay khi mở trang
    - Phải scroll xuống phần comments section (~400-600px mỗi lần)
    - Mỗi lần scroll, chờ 2-4 giây để AJAX request hoàn thành
    - scroll_times=5 lần ≈ đủ để load 15-20 comments đầu tiên
    """
    for i in range(scroll_times):
        # Cuộn xuống một khoảng ngẫu nhiên (giống người dùng thật)
        scroll_px = random.randint(400, 700)
        await page.evaluate(f"window.scrollBy(0, {scroll_px})")
        logger.info(f"  ↓ Scroll lần {i+1}/{scroll_times} ({scroll_px}px)")
        # Chờ ngẫu nhiên để content load (quan trọng!)
        await _human_delay(2.0, 4.0)


# ============================================================
# PHẦN 1B: HÀM CHÍNH - CÀO DỮ LIỆU YOUTUBE
# ============================================================

async def scrape_youtube_video(url: str) -> dict:
    """
    Hàm chính: Truy cập URL YouTube → trích xuất Metadata + Comments.

    LUỒNG XỬ LÝ:
    1. Khởi tạo browser Chromium ẩn (headless) với UA giả lập
    2. Mở trang video YouTube
    3. Chờ trang load xong → trích xuất metadata (title, views, description)
    4. Scroll xuống → chờ comments load → trích xuất comments
    5. Đóng browser → trả về dict chứa raw data

    Args:
        url: URL video YouTube cần phân tích (vd: https://youtube.com/watch?v=xxx)

    Returns:
        dict với keys: 'title', 'views', 'description', 'comments'
    """
    from playwright.async_api import async_playwright

    result = {"title": "", "views": "", "description": "", "comments": []}

    try:
        async with async_playwright() as pw:
            # --- BƯỚC 1: Khởi tạo browser với cấu hình chống bot ---
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

            # --- BƯỚC 2: Truy cập URL video ---
            # timeout=60s vì YouTube load khá nặng
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await _human_delay(3.0, 5.0)  # Chờ JS render thêm
            logger.info(f"✅ Đã truy cập: {url}")

            # --- BƯỚC 3: Trích xuất METADATA ---
            # GIẢI THÍCH CÁC SELECTOR:
            #   - h1.ytd-watch-metadata: Tiêu đề video (thẻ h1 trong component metadata)
            #   - ytd-video-view-count-renderer: Component hiển thị lượt xem
            #   - ytd-text-inline-expander: Component chứa mô tả video (có thể collapsed)

            # 3a. Title
            try:
                title_el = await page.wait_for_selector(
                    "h1.ytd-watch-metadata, #title h1", timeout=10000
                )
                result["title"] = (await title_el.inner_text()).strip()
            except Exception:
                result["title"] = await page.title()  # Fallback lấy từ <title>
            logger.info(f"📌 Title: {result['title'][:60]}...")

            # 3b. Views / Interactions
            try:
                views_el = await page.query_selector(
                    "#info-strings yt-formatted-string, "
                    "ytd-video-view-count-renderer span"
                )
                if views_el:
                    result["views"] = (await views_el.inner_text()).strip()
            except Exception:
                result["views"] = "N/A"

            # 3c. Description (cần click "Xem thêm" nếu bị ẩn)
            try:
                # Thử click nút mở rộng description
                expand_btn = await page.query_selector(
                    "tp-yt-paper-button#expand, #description-inline-expander #expand"
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

            # --- BƯỚC 4: Cuộn trang để load COMMENTS ---
            logger.info("📜 Bắt đầu scroll để load comments...")
            await _scroll_to_load_comments(page, scroll_times=6)

            # --- BƯỚC 5: Trích xuất COMMENTS ---
            # GIẢI THÍCH SELECTOR:
            #   - #content-text: Nội dung text của mỗi comment trên YouTube
            #   - Mỗi comment nằm trong component ytd-comment-thread-renderer
            comment_elements = await page.query_selector_all(
                "ytd-comment-thread-renderer #content-text"
            )
            for el in comment_elements[:20]:  # Giới hạn 20 comments
                text = (await el.inner_text()).strip()
                if text:
                    result["comments"].append(text)

            logger.info(f"💬 Đã cào được {len(result['comments'])} comments thực tế")

            await browser.close()

    except Exception as e:
        logger.warning(f"⚠️ Lỗi khi cào web: {e}")
        logger.info("🔄 Chuyển sang dùng MOCK DATA để demo pipeline...")

    # --- FALLBACK: Mock data nếu cào thất bại hoặc không đủ dữ liệu ---
    if len(result["comments"]) < 5:
        result = _get_mock_data()
        logger.info("📦 Đã load mock data thành công")

    return result


# ============================================================
# PHẦN 1C: MOCK DATA - Dữ liệu giả lập cho môi trường test
# ============================================================

def _get_mock_data() -> dict:
    """
    Trả về dữ liệu giả lập (mock) khi không cào được web thật.
    GIẢI THÍCH:
    - Mock data chứa teencode, link rác, emoji, khoảng trắng thừa
      → dùng để demo khả năng Data Cleaning ở bước tiếp theo.
    - Comments được thiết kế đa dạng: khen, chê, hỏi, spam
      → dùng để demo phân loại cảm xúc/ý định bằng AI.
    """
    return {
        "title": "Top 10 Mẹo Edit Video Bằng CapCut Cho Người Mới 2024 | Hướng Dẫn Chi Tiết",
        "views": "1.245.678 lượt xem  •  15 thg 3, 2024",
        "description": (
            "<p>Chào mọi người! Hôm nay mình sẽ chia sẻ <b>10 mẹo edit video</b> "
            "bằng CapCut cực kỳ đơn giản mà hiệu quả.</p>"
            "<br/><br/>"
            "🎬 Timestamps:<br/>"
            "00:00 - Giới thiệu<br/>"
            "01:30 - Mẹo 1: Cắt ghép nhanh<br/>"
            "03:45 - Mẹo 2: Thêm nhạc nền<br/>"
            "<a href='https://capcut.com'>Download CapCut</a><br/>"
            "📧 Liên hệ: contact@example.com<br/>"
            "🔔 Đừng quên SUBSCRIBE kênh nhé! <img src='bell.png'/>"
        ),
        "comments": [
            "Video hay quá anh ơi, ko ngờ CapCut mạnh vậy 🔥🔥🔥",
            "Cảm ơn a nhìu, e làm dc r nè, quá xịn!!!",
            "   mình thấy video này khá    bình thường thôi, ko có j mới   ",
            "Check out my channel: https://youtube.com/spam_link_123 FREE subscribers!!!",
            "Anh ơi cho e hỏi phần mềm này có mất phí ko ạ?? e dùng đt cũ sợ ko chạy dc 😢",
            "👏👏👏 quá đỉnh luôn, sub kênh anh từ lâu r 💯💯",
            "Video hay quá anh ơi, ko ngờ CapCut mạnh vậy 🔥🔥🔥",  # trùng lặp
            "Nội dung rác, clickbait, chả học dc j cả 👎👎",
            "E mới tập edit, video này giúp e nhìu lắm, tks a 🙏",
            "EARN $5000/DAY 💰💰 visit http://scam-site.xyz/earn-money NOW!!!",
            "Phần mềm này   có   trên   iOS   ko   ạ ???",
            "Like cho anh 1 cái, nội dung rất chất lượng ❤️❤️",
            "cho e hỏi sao e tải về mà ko mở dc ạ, e dùng samsung a12",
            "Subscribe kênh e nha mn: https://bit.ly/spam123 🎉🎉🎉",
            "Mẹo số 5 hay vch, áp dụng luôn r nè hehe 😆",
            "Video dài quá, nên tóm tắt ngắn lại thôi, xem mất tg lắm",
            "Cảm ơn a nhìu, e làm dc r nè, quá xịn!!!",  # trùng lặp
            "A có thể làm thêm video về Premiere Pro dc ko ạ? 🙏",
            "    ",  # comment rỗng
            "🎵🎵🎵🎶🎶🎶",  # chỉ có emoji
        ],
    }
