"""
╔══════════════════════════════════════════════════════════════════╗
║  MODULE 3: AI ANALYZER - Prompt Engineering & API Optimization   ║
║  Tác giả: Senior AI Data Engineer                                ║
║  Mục đích: Dùng LLM phân tích metadata + comments đã sạch       ║
╚══════════════════════════════════════════════════════════════════╝

GIẢI THÍCH CHO SẾP VỀ TỐI ƯU CHI PHÍ API:
- Mỗi lần gọi API tốn tiền theo số TOKEN (đơn vị đo độ dài text).
- Kỹ thuật BATCHING: Gộp 15-20 comments vào 1 lần gọi thay vì
  gọi 15-20 lần riêng → TIẾT KIỆM 90%+ chi phí API.
- Ép JSON output: Tránh AI trả về text tự do → phải parse lại → tốn thêm 1 lần gọi.
- Temperature thấp (0.1): Giảm tính "sáng tạo" → kết quả nhất quán, dễ parse.
"""

import json
import logging
import os
from openai import OpenAI

logger = logging.getLogger(__name__)


# ============================================================
# PHẦN 3A: PROMPT TEMPLATES
# ============================================================
# GIẢI THÍCH THIẾT KẾ PROMPT:
# Mỗi prompt có 2 phần: System (vai trò + quy tắc) và User (dữ liệu + yêu cầu)
# System prompt KHÔNG thay đổi giữa các lần gọi → có thể cache
# User prompt thay đổi theo dữ liệu đầu vào

# --- PROMPT 1: Phân tích Metadata ---
METADATA_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích nội dung YouTube.
Nhiệm vụ: Phân tích metadata của video đối thủ cạnh tranh.

QUY TẮC BẮT BUỘC:
1. Trả lời ĐÚNG bằng JSON object, KHÔNG thêm text ngoài JSON.
2. JSON phải có đúng 3 keys: "chu_de_chinh", "tu_khoa", "tom_tat"
3. "tu_khoa" là mảng ĐÚNG 3 từ khóa quan trọng nhất.
4. "tom_tat" là string tóm tắt nội dung trong 2-3 câu.
5. Phân tích bằng tiếng Việt."""

METADATA_USER_TEMPLATE = """Phân tích metadata video YouTube sau:

TIÊU ĐỀ: {title}
LƯỢT XEM: {views}
MÔ TẢ: {description}

Trả về JSON object với format:
{{
  "chu_de_chinh": "...",
  "tu_khoa": ["keyword1", "keyword2", "keyword3"],
  "tom_tat": "..."
}}"""

# --- PROMPT 2: Phân tích Comments (BATCHING) ---
# GIẢI THÍCH KỸ THUẬT BATCHING:
# Thay vì gửi từng comment riêng lẻ (N lần gọi API = N x $$$),
# ta gộp TẤT CẢ comments vào 1 prompt duy nhất (1 lần gọi = 1 x $$$).
# Đánh số [1], [2], [3]... để AI biết đâu là ranh giới giữa các comment.

COMMENTS_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích bình luận mạng xã hội.
Nhiệm vụ: Phân loại cảm xúc và ý định của TỪNG bình luận YouTube.

QUY TẮC BẮT BUỘC:
1. Trả lời ĐÚNG bằng JSON object, KHÔNG thêm text ngoài JSON.
2. JSON có key "comments" là mảng các object.
3. Mỗi object có đúng 4 keys:
   - "stt": số thứ tự (integer)
   - "noi_dung": nội dung gốc (string)
   - "cam_xuc": một trong ["Tích cực", "Tiêu cực", "Trung lập"]
   - "y_dinh": một trong ["Khen ngợi", "Chê bai", "Hỏi đáp", "Spam"]
4. Phân tích bằng tiếng Việt.
5. KHÔNG bỏ sót bình luận nào."""

COMMENTS_USER_TEMPLATE = """Phân loại cảm xúc và ý định cho {count} bình luận sau:

{numbered_comments}

Trả về JSON object với format:
{{
  "comments": [
    {{"stt": 1, "noi_dung": "...", "cam_xuc": "...", "y_dinh": "..."}},
    ...
  ]
}}"""


# ============================================================
# PHẦN 3B: GỌI API VỚI TỐI ƯU CHI PHÍ
# ============================================================

def analyze_metadata(metadata: dict, client: OpenAI) -> dict:
    """
    Gọi API để phân tích metadata video.

    TỐI ƯU:
    - temperature=0.1: Kết quả deterministic, ít "ảo" → dễ parse JSON
    - response_format=json_object: ÉP BUỘC AI trả JSON → không cần regex parse
    - max_tokens=500: Giới hạn output → tránh AI "lan man" tốn token

    Args:
        metadata: dict chứa title, views, description đã sạch
        client: OpenAI client instance (BẮT BUỘC)

    Returns:
        dict chứa kết quả phân tích (chủ đề, từ khóa, tóm tắt)

    Raises:
        ValueError: Khi không có OpenAI client
        RuntimeError: Khi API call thất bại
    """
    if client is None:
        raise ValueError("Cần cung cấp OPENAI_API_KEY để chạy phân tích AI")

    logger.info("🤖 Gọi API phân tích Metadata...")

    user_prompt = METADATA_USER_TEMPLATE.format(
        title=metadata["title"],
        views=metadata["views"],
        description=metadata["description"][:500],  # Cắt description dài → tiết kiệm token
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Model rẻ nhất có hỗ trợ JSON mode
            messages=[
                {"role": "system", "content": METADATA_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"  ✅ Chủ đề: {result.get('chu_de_chinh', 'N/A')}")
        return result

    except Exception as e:
        logger.error(f"  ❌ Lỗi API Metadata: {e}")
        raise RuntimeError(f"API call thất bại: {e}") from e


def analyze_comments_batch(comments: list, client: OpenAI) -> dict:
    """
    Gọi API phân tích TẤT CẢ comments trong 1 lần (BATCHING).

    GIẢI THÍCH KỸ THUẬT BATCHING CHO SẾP:
    ┌─────────────────────────────────────────────────────────┐
    │ CÁCH THÔNG THƯỜNG (Không tối ưu):                       │
    │   15 comments × 1 API call = 15 API calls               │
    │   Chi phí ước tính: 15 × $0.003 = $0.045                │
    │                                                         │
    │ CÁCH TỐI ƯU (Batching):                                 │
    │   15 comments gộp → 1 API call = 1 API call             │
    │   Chi phí ước tính: 1 × $0.005 = $0.005                 │
    │                                                         │
    │ → TIẾT KIỆM: ~89% chi phí API                           │
    └─────────────────────────────────────────────────────────┘

    Args:
        comments: Danh sách comments đã sạch
        client: OpenAI client instance (BẮT BUỘC)

    Returns:
        dict chứa mảng comments đã phân loại

    Raises:
        ValueError: Khi không có OpenAI client
        RuntimeError: Khi API call thất bại
    """
    if client is None:
        raise ValueError("Cần cung cấp OPENAI_API_KEY để chạy phân tích AI")

    logger.info(f"🤖 Gọi API phân tích {len(comments)} comments (BATCHED)...")

    # --- Đánh số comments để AI phân biệt ranh giới ---
    numbered = "\n".join(
        f"[{i+1}] {comment}" for i, comment in enumerate(comments)
    )

    user_prompt = COMMENTS_USER_TEMPLATE.format(
        count=len(comments),
        numbered_comments=numbered,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": COMMENTS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2000,  # Comments nhiều → cần nhiều token hơn
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"  ✅ Đã phân tích {len(result.get('comments', []))} comments")
        return result

    except Exception as e:
        logger.error(f"  ❌ Lỗi API Comments: {e}")
        raise RuntimeError(f"API call thất bại: {e}") from e
