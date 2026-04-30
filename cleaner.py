"""
╔══════════════════════════════════════════════════════════════════╗
║  MODULE 2: DATA CLEANING - Làm sạch dữ liệu bằng Regex         ║
║  Tác giả: Senior AI Data Engineer                                ║
║  Mục đích: Chuẩn hóa raw data trước khi gửi cho AI phân tích    ║
╠══════════════════════════════════════════════════════════════════╣
║  CÔNG NGHỆ: Python re (regex), pandas                           ║
║  CHI PHÍ: 0 đồng — toàn bộ xử lý offline, không gọi API        ║
╚══════════════════════════════════════════════════════════════════╝

GIẢI THÍCH TẠI SAO CẦN BƯỚC NÀY:
- Dữ liệu cào từ web luôn "bẩn": chứa HTML tags, link spam, teencode,
  emoji thừa, khoảng trắng lộn xộn, bình luận trùng lặp.
- NẾU KHÔNG LÀM SẠCH trước khi gửi AI:
  → Tốn token (tốn tiền API) cho dữ liệu rác
  → Kết quả phân tích sai lệch
  → JSON output bị lỗi format
- Module này dùng REGEX (Regular Expression) để xử lý chuỗi NHANH,
  KHÔNG cần gọi AI → TIẾT KIỆM 100% chi phí cho bước tiền xử lý.
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)


# ============================================================
# PHẦN 2A: TỪ ĐIỂN TEENCODE TIẾNG VIỆT
# ============================================================
# GIẢI THÍCH:
# Teencode là cách viết tắt phổ biến trên mạng xã hội Việt Nam.
# Nếu không chuẩn hóa, AI sẽ hiểu sai ngữ nghĩa hoặc bỏ qua.
# Ví dụ: "ko dc" → AI có thể không hiểu = "không được"
# Từ điển mapping teencode → tiếng Việt chuẩn.
# Sắp xếp xử lý theo độ dài giảm dần để tránh replace nhầm.

TEENCODE_MAP = {
    # 4+ ký tự (xử lý trước)
    "nhìu": "nhiều",
    "nhiu": "nhiều",
    # 3 ký tự
    "vch": "vãi chưởng",
    "tks": "thanks",
    "bth": "bình thường",
    "mik": "mình",
    "đag": "đang",
    # 2 ký tự
    "ko": "không",
    "kg": "không",
    "dc": "được",
    "đc": "được",
    "mk": "mình",
    "bn": "bạn",
    "ns": "nói",
    "tk": "thanks",
    "lm": "làm",
    "đt": "điện thoại",
    "mn": "mọi người",
    "tg": "thời gian",
    "bt": "bình thường",
    "vs": "với",
    "cx": "cũng",
    "ng": "người",
    "nt": "nhắn tin",
    # 1 ký tự (xử lý cuối cùng — cần cẩn thận với word boundary)
    "k": "không",
    "j": "gì",
    "r": "rồi",
    "a": "anh",
    "e": "em",
}


# ============================================================
# PHẦN 2B: HÀM LÀM SẠCH METADATA
# ============================================================

def clean_metadata(title: str, views: str, description: str) -> dict:
    """
    Làm sạch metadata video: xóa HTML tags, URL, email, chuẩn hóa text.

    GIẢI THÍCH REGEX TỪNG BƯỚC:
    - <[^>]+>  : Match mọi HTML tag (vd: <p>, <br/>, <a href="...">)
                  [^>]+ = 1 hoặc nhiều ký tự KHÔNG phải dấu >
    - https?://\\S+ : Match URL bắt đầu bằng http hoặc https
    - \\S+@\\S+\\.\\S+ : Match email pattern (chuỗi@chuỗi.chuỗi)
    - \\s{2,}  : Match 2+ khoảng trắng liên tiếp → gộp thành 1

    Args:
        title: Tiêu đề video (raw)
        views: Chuỗi lượt xem (raw, vd: "1.245.678 lượt xem")
        description: Mô tả video (raw, có thể chứa HTML)

    Returns:
        dict chứa metadata đã làm sạch: title, views, description
    """
    logger.info("🧹 Bắt đầu làm sạch Metadata...")

    # --- Bước 1: Xóa tất cả HTML tags trong description ---
    # Regex: <[^>]+> = "bắt đầu bằng <, 1+ ký tự không phải >, kết thúc bằng >"
    clean_desc = re.sub(r'<[^>]+>', ' ', description)

    # --- Bước 2: Xóa URL/link trong description ---
    # Regex: https?://\S+ = "http(s):// + 1+ ký tự không phải khoảng trắng"
    clean_desc = re.sub(r'https?://\S+', '', clean_desc)

    # --- Bước 3: Xóa email addresses ---
    # Regex: \S+@\S+\.\S+ = "chuỗi@chuỗi.chuỗi" (pattern email cơ bản)
    clean_desc = re.sub(r'\S+@\S+\.\S+', '', clean_desc)

    # --- Bước 4: Gộp khoảng trắng thừa + xóa đầu/cuối ---
    clean_desc = re.sub(r'\s{2,}', ' ', clean_desc).strip()

    # --- Bước 5: Xóa emoji khỏi title (giữ text thuần túy cho AI) ---
    clean_title = _remove_emojis(title).strip()
    clean_title = re.sub(r'\s{2,}', ' ', clean_title)

    # --- Bước 6: Trích xuất số lượt xem (chỉ giữ lại phần số) ---
    # Regex: [\d.]+ = 1+ chữ số hoặc dấu chấm (vd: "1.245.678")
    view_str = views.replace(',', '.') if views else ''
    view_match = re.search(r'[\d.]+', view_str)
    clean_views = view_match.group(0) if view_match else "N/A"

    result = {
        "title": clean_title,
        "views": clean_views,
        "description": clean_desc,
    }

    logger.info(f"  ✅ Title: {clean_title[:50]}...")
    logger.info(f"  ✅ Views: {clean_views}")
    logger.info(f"  ✅ Description: {len(clean_desc)} ký tự (sau khi xóa HTML/URL)")

    return result


# ============================================================
# PHẦN 2C: HÀM LÀM SẠCH COMMENTS
# ============================================================

def clean_comments(raw_comments: List[str]) -> List[str]:
    """
    Pipeline làm sạch toàn bộ danh sách comments.

    LUỒNG XỬ LÝ (theo thứ tự ưu tiên):
    1. Xóa link spam/URL         → loại nội dung quảng cáo
    2. Xóa emoji và ký tự đặc biệt → giữ text thuần túy
    3. Chuẩn hóa teencode → tiếng Việt → AI hiểu đúng ngữ nghĩa
    4. Gộp khoảng trắng thừa     → text gọn gàng
    5. Loại comments rỗng/quá ngắn → bỏ noise
    6. Loại comments TRÙNG LẶP   → deduplicate

    GIẢI THÍCH TẠI SAO THỨ TỰ QUAN TRỌNG:
    - Xóa URL TRƯỚC emoji: URL chứa ký tự đặc biệt, xóa trước tránh nhầm
    - Xóa emoji TRƯỚC teencode: emoji dính vào chữ gây nhầm word boundary
    - Deduplicate SAU CÙNG: 2 comment khác nhau có thể trở thành giống nhau
      sau khi clean (vd: "Ko dc 😭" và "ko dc" → cùng = "không được")

    Args:
        raw_comments: Danh sách comments thô từ bước scraping

    Returns:
        Danh sách comments đã làm sạch (không trùng lặp)
    """
    logger.info(f"🧹 Bắt đầu làm sạch {len(raw_comments)} comments...")

    cleaned = []
    for comment in raw_comments:
        c = _clean_single_comment(comment)
        # Loại bỏ comment rỗng hoặc quá ngắn (< 3 ký tự = không có ý nghĩa)
        if c and len(c) >= 3:
            cleaned.append(c)

    # --- Bước cuối: Loại bỏ trùng lặp (giữ nguyên thứ tự xuất hiện) ---
    # GIẢI THÍCH: Dùng dict.fromkeys() thay vì set() để GIỮ THỨ TỰ
    # set() không đảm bảo thứ tự → mất context thời gian của comments
    deduplicated = list(dict.fromkeys(cleaned))

    removed = len(raw_comments) - len(deduplicated)
    logger.info(f"  ✅ Đã loại bỏ {removed} comments (rỗng/trùng/spam)")
    logger.info(f"  ✅ Còn lại {len(deduplicated)} comments sạch")

    return deduplicated


def _clean_single_comment(text: str) -> str:
    """
    Làm sạch MỘT comment đơn lẻ qua nhiều bước lọc.

    Mỗi re.sub() là một "bộ lọc" — data chạy qua từng bộ lọc theo thứ tự.

    Args:
        text: Nội dung comment thô

    Returns:
        Comment đã làm sạch (string)
    """
    # ── Bước 1: Xóa URL/link spam ──
    # Pattern: http(s)://... hoặc www.xxx hoặc bit.ly/xxx
    text = re.sub(r'https?://\S+', '', text)   # Full URLs
    text = re.sub(r'www\.\S+', '', text)       # URLs bắt đầu bằng www
    text = re.sub(r'bit\.ly/\S+', '', text)    # Short links (bit.ly)

    # ── Bước 2: Xóa emoji và ký tự Unicode đặc biệt ──
    text = _remove_emojis(text)

    # ── Bước 3: Chuẩn hóa teencode tiếng Việt ──
    text = _normalize_teencode(text)

    # ── Bước 4: Xóa ký tự đặc biệt lặp (vd: "!!!" → "!", "???" → "?") ──
    # Regex: ([!?.]) = capture 1 ký tự, {2,} = lặp 2+ lần
    text = re.sub(r'([!?.]){2,}', r'\1', text)

    # ── Bước 5: Gộp khoảng trắng thừa + trim đầu/cuối ──
    text = re.sub(r'\s{2,}', ' ', text).strip()

    return text


# ============================================================
# PHẦN 2D: HÀM TIỆN ÍCH (Utility Functions)
# ============================================================

def _remove_emojis(text: str) -> str:
    """
    Xóa tất cả emoji/icon Unicode khỏi chuỗi.

    GIẢI THÍCH REGEX:
    Emoji nằm trong các Unicode range đặc biệt:
    - U+1F600-1F64F : Emoticons (mặt cười, buồn, giận...)
    - U+1F300-1F5FF : Misc Symbols (thời tiết, đồ vật, cây cối...)
    - U+1F680-1F6FF : Transport (xe, máy bay, tàu...)
    - U+1F1E0-1F1FF : Cờ quốc gia (🇻🇳, 🇺🇸...)
    - U+2600-26FF   : Misc Symbols (♠, ♥, ☀, ☂...)
    - U+2700-27BF   : Dingbats (✂, ✈, ✉, ✓...)
    - U+FE00-FE0F   : Variation Selectors (modifier cho emoji)
    - U+1F900-1F9FF : Supplemental Symbols (🤔, 🤗...)
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Misc Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map
        "\U0001F1E0-\U0001F1FF"  # Cờ quốc gia
        "\U00002600-\U000026FF"  # Misc Symbols
        "\U00002700-\U000027BF"  # Dingbats
        "\U0000FE00-\U0000FE0F"  # Variation Selectors
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U00002702-\U000027B0"  # Dingbats (mở rộng)
        "\U000024C2-\U0001F251"  # Enclosed characters
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub('', text)


def _normalize_teencode(text: str) -> str:
    """
    Thay thế teencode tiếng Việt bằng từ chuẩn.

    GIẢI THÍCH KỸ THUẬT:
    - Dùng word boundary \\b để TRÁNH replace nhầm:
      Ví dụ: "không" chứa "ko" nhưng \\bko\\b chỉ match "ko" đứng riêng
    - Sắp xếp dict theo độ dài key GIẢM DẦN:
      "nhìu" (4 ký tự) phải được xử lý TRƯỚC "j" (1 ký tự)
      để tránh conflict
    - re.IGNORECASE: match cả "Ko", "KO", "ko"

    Args:
        text: Chuỗi cần chuẩn hóa

    Returns:
        Chuỗi đã thay teencode bằng tiếng Việt chuẩn
    """
    # Sắp xếp theo độ dài giảm dần (từ dài xử lý trước, từ ngắn xử lý sau)
    sorted_items = sorted(
        TEENCODE_MAP.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    )

    for teencode, standard in sorted_items:
        # \b = word boundary: chỉ match khi teencode đứng riêng thành 1 từ
        pattern = r'\b' + re.escape(teencode) + r'\b'
        text = re.sub(pattern, standard, text, flags=re.IGNORECASE)

    return text
