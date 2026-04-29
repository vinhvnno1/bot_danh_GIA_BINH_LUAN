"""
╔══════════════════════════════════════════════════════════════════╗
║  MODULE 2: DATA CLEANING - Làm sạch dữ liệu bằng Regex         ║
║  Tác giả: Senior AI Data Engineer                                ║
║  Mục đích: Chuẩn hóa raw data trước khi gửi cho AI phân tích    ║
╚══════════════════════════════════════════════════════════════════╝

GIẢI THÍCH CHO SẾP:
- Dữ liệu cào từ web luôn "bẩn": chứa HTML tags, link spam, teencode,
  emoji thừa, khoảng trắng lộn xộn, bình luận trùng lặp.
- NẾU KHÔNG LÀM SẠCH trước khi gửi AI → tốn token (tốn tiền API),
  kết quả phân tích sai lệch, JSON output bị lỗi format.
- Module này dùng REGEX (Regular Expression) để xử lý chuỗi nhanh,
  KHÔNG cần gọi AI → tiết kiệm 100% chi phí cho bước tiền xử lý.
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
# Từ điển này mapping teencode → tiếng Việt chuẩn.
# Sắp xếp theo độ dài giảm dần để tránh replace nhầm (vd: "bth" trước "bt")

TEENCODE_MAP = {
    "ko": "không", "kg": "không", "k": "không",
    "dc": "được", "đc": "được",
    "mk": "mình", "mik": "mình",
    "bn": "bạn",
    "ns": "nói",
    "vch": "vãi chưởng",
    "tks": "thanks", "tk": "thanks",
    "nhìu": "nhiều", "nhiu": "nhiều",
    "lm": "làm",
    "đt": "điện thoại",
    "j": "gì",
    "r": "rồi",
    "a": "anh", "e": "em",
    "mn": "mọi người",
    "tg": "thời gian",
    "bth": "bình thường", "bt": "bình thường",
    "vs": "với",
    "cx": "cũng",
    "ng": "người",
    "nt": "nhắn tin",
    "đag": "đang",
}


# ============================================================
# PHẦN 2B: HÀM LÀM SẠCH METADATA
# ============================================================

def clean_metadata(title: str, views: str, description: str) -> dict:
    """
    Làm sạch metadata video: xóa HTML tags, chuẩn hóa text.

    GIẢI THÍCH REGEX TỪNG DÒNG:
    - <[^>]+>  : Match mọi HTML tag (vd: <p>, <br/>, <a href="...">)
                  [^>]+ = 1 hoặc nhiều ký tự KHÔNG phải dấu >
    - \\s{2,}  : Match 2+ khoảng trắng liên tiếp → gộp thành 1
    - ^\\s+|\\s+$ : Xóa khoảng trắng đầu/cuối chuỗi (trim)

    Args:
        title: Tiêu đề video (raw)
        views: Chuỗi lượt xem (raw, vd: "1.245.678 lượt xem")
        description: Mô tả video (raw, có thể chứa HTML)

    Returns:
        dict chứa metadata đã làm sạch
    """
    logger.info("🧹 Bắt đầu làm sạch Metadata...")

    # --- Bước 1: Xóa tất cả HTML tags trong description ---
    # Regex: <[^>]+> nghĩa là "bắt đầu bằng <, theo sau bởi 1+ ký tự
    # không phải >, kết thúc bằng >" → match <p>, </p>, <br/>, <img src="..."/>
    clean_desc = re.sub(r'<[^>]+>', ' ', description)

    # --- Bước 2: Xóa URL/link trong description ---
    # Regex: https?://\S+ nghĩa là "http hoặc https, theo sau bởi ://,
    # rồi 1+ ký tự không phải khoảng trắng"
    clean_desc = re.sub(r'https?://\S+', '', clean_desc)

    # --- Bước 3: Xóa email addresses ---
    # Regex: \S+@\S+\.\S+ = "chuỗi@chuỗi.chuỗi" (pattern email cơ bản)
    clean_desc = re.sub(r'\S+@\S+\.\S+', '', clean_desc)

    # --- Bước 4: Gộp khoảng trắng thừa ---
    clean_desc = re.sub(r'\s{2,}', ' ', clean_desc).strip()

    # --- Bước 5: Xóa emoji khỏi title (giữ text thuần túy) ---
    clean_title = _remove_emojis(title).strip()
    clean_title = re.sub(r'\s{2,}', ' ', clean_title)

    # --- Bước 6: Trích xuất số lượt xem (chỉ lấy số) ---
    # Regex: [\d.]+ = 1+ chữ số hoặc dấu chấm (vd: "1.245.678")
    view_match = re.search(r'[\d.]+', views.replace(',', '.') if views else '')
    clean_views = view_match.group(0) if view_match else "N/A"

    result = {
        "title": clean_title,
        "views": clean_views,
        "description": clean_desc,
    }
    logger.info(f"  ✅ Title: {clean_title[:50]}...")
    logger.info(f"  ✅ Views: {clean_views}")
    logger.info(f"  ✅ Description: {len(clean_desc)} ký tự (sau khi xóa HTML)")
    return result


# ============================================================
# PHẦN 2C: HÀM LÀM SẠCH COMMENTS
# ============================================================

def clean_comments(raw_comments: List[str]) -> List[str]:
    """
    Pipeline làm sạch toàn bộ danh sách comments.

    LUỒNG XỬ LÝ (theo thứ tự):
    1. Xóa link spam/URL
    2. Xóa emoji và ký tự đặc biệt
    3. Chuẩn hóa teencode → tiếng Việt
    4. Gộp khoảng trắng thừa
    5. Loại bỏ comments rỗng hoặc quá ngắn (< 3 ký tự)
    6. Loại bỏ comments TRÙNG LẶP (deduplicate)

    GIẢI THÍCH TẠI SAO THỨ TỰ QUAN TRỌNG:
    - Phải xóa URL TRƯỚC khi xóa emoji, vì URL có thể chứa ký tự đặc biệt
    - Phải xóa emoji TRƯỚC khi chuẩn hóa teencode, vì emoji có thể dính vào chữ
    - Phải deduplicate SAU CÙNG, vì sau khi clean 2 comment khác nhau
      có thể trở thành giống nhau

    Args:
        raw_comments: Danh sách comments thô từ bước scraping

    Returns:
        Danh sách comments đã làm sạch (không trùng lặp)
    """
    logger.info(f"🧹 Bắt đầu làm sạch {len(raw_comments)} comments...")

    cleaned = []
    for i, comment in enumerate(raw_comments):
        c = _clean_single_comment(comment)
        if c and len(c) >= 3:  # Loại bỏ comment rỗng hoặc quá ngắn
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
    Làm sạch MỘT comment đơn lẻ.

    GIẢI THÍCH TỪNG BƯỚC REGEX:
    Mỗi re.sub() là một "bộ lọc", data chạy qua từng bộ lọc theo thứ tự.
    """
    # Bước 1: Xóa URL/link spam
    # Pattern: http(s)://... hoặc www.xxx hoặc bit.ly/xxx
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'bit\.ly/\S+', '', text)

    # Bước 2: Xóa emoji và ký tự Unicode đặc biệt
    text = _remove_emojis(text)

    # Bước 3: Chuẩn hóa teencode tiếng Việt
    text = _normalize_teencode(text)

    # Bước 4: Xóa ký tự đặc biệt lặp (vd: "!!!" → "!", "???" → "?")
    text = re.sub(r'([!?.]){2,}', r'\1', text)

    # Bước 5: Gộp khoảng trắng thừa + trim
    text = re.sub(r'\s{2,}', ' ', text).strip()

    return text


def _remove_emojis(text: str) -> str:
    """
    Xóa tất cả emoji/icon Unicode khỏi chuỗi.

    GIẢI THÍCH REGEX:
    Emoji nằm trong các Unicode range đặc biệt:
    - U+1F600-1F64F : Emoticons (mặt cười, buồn...)
    - U+1F300-1F5FF : Misc Symbols (thời tiết, đồ vật...)
    - U+1F680-1F6FF : Transport (xe, máy bay...)
    - U+1F1E0-1F1FF : Cờ quốc gia
    - U+2600-26FF   : Misc Symbols (♠, ♥, ☀...)
    - U+2700-27BF   : Dingbats (✂, ✈, ✉...)
    - U+FE00-FE0F   : Variation Selectors
    - U+1F900-1F9FF : Supplemental Symbols
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002600-\U000026FF"
        "\U00002700-\U000027BF"
        "\U0000FE00-\U0000FE0F"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub('', text)


def _normalize_teencode(text: str) -> str:
    """
    Thay thế teencode tiếng Việt bằng từ chuẩn.

    GIẢI THÍCH KỸ THUẬT QUAN TRỌNG:
    - Dùng word boundary \\b để TRÁNH replace nhầm:
      Ví dụ: "không" chứa "ko" nhưng \\bko\\b chỉ match "ko" đứng riêng
    - Sắp xếp dict theo độ dài key giảm dần:
      "nhìu" (4 ký tự) phải được xử lý TRƯỚC "j" (1 ký tự)
      để tránh conflict
    - re.IGNORECASE: match cả "Ko", "KO", "ko"
    """
    # Sắp xếp theo độ dài giảm dần (dài trước, ngắn sau)
    sorted_items = sorted(TEENCODE_MAP.items(), key=lambda x: len(x[0]), reverse=True)

    for teencode, standard in sorted_items:
        # \b = word boundary: chỉ match khi teencode là 1 từ riêng biệt
        pattern = r'\b' + re.escape(teencode) + r'\b'
        text = re.sub(pattern, standard, text, flags=re.IGNORECASE)

    return text
