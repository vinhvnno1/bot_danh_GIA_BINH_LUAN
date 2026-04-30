"""
╔══════════════════════════════════════════════════════════════════╗
║  MODULE 3: AI ANALYZER - Prompt Engineering & NVIDIA NIM API     ║
║  Tác giả: Senior AI Data Engineer                                ║
║  Mục đích: Dùng NVIDIA NIM phân tích metadata + comments đã sạch║
╠══════════════════════════════════════════════════════════════════╣
║  CÔNG NGHỆ: NVIDIA NIM API (OpenAI-compatible)                  ║
║  MODEL: meta/llama-3.1-405b-instruct (hoặc model khác trên NIM) ║
║  TỐI ƯU: BATCHING tất cả vào 1 lần gọi API duy nhất            ║
╚══════════════════════════════════════════════════════════════════╝

GIẢI THÍCH VỀ TỐI ƯU CHI PHÍ API:
- Mỗi lần gọi API tốn tiền theo số TOKEN (đơn vị đo độ dài text).
- Kỹ thuật BATCHING: Gộp Metadata + TẤT CẢ Comments vào CÙNG 1 prompt
  → CHỈ TỐN 1 LẦN GỌI API thay vì N+1 lần → TIẾT KIỆM ~95% chi phí.
- Ép JSON output: Yêu cầu AI trả về JSON chuẩn → không cần parse lại.
- Temperature thấp (0.1): Giảm tính "sáng tạo" → kết quả nhất quán.

NVIDIA NIM API:
- Endpoint: https://integrate.api.nvidia.com/v1
- Dùng OpenAI SDK (openai) — KHÔNG cần thư viện riêng
- API key lấy tại: https://build.nvidia.com
- Key format: nvapi-...
- Free tier: 1000 credits miễn phí khi đăng ký

SO SÁNH CHI PHÍ:
┌─────────────────────────────────────────────────────────────┐
│ CÁCH THÔNG THƯỜNG (Không tối ưu):                           │
│   1 API call metadata + 20 API calls comments = 21 calls    │
│   Chi phí ước tính: 21 × $0.003 = $0.063                    │
│                                                              │
│ CÁCH TỐI ƯU LV1 (Batching comments):                        │
│   1 call metadata + 1 call tất cả comments = 2 calls        │
│   Chi phí ước tính: 2 × $0.005 = $0.010                     │
│                                                              │
│ CÁCH TỐI ƯU LV2 (Super Batching - code này):                │
│   1 call DUY NHẤT cho cả metadata + comments = 1 call       │
│   Chi phí ước tính: 1 × $0.007 = $0.007                     │
│                                                              │
│ → TIẾT KIỆM: ~89% so với cách thông thường                  │
└─────────────────────────────────────────────────────────────┘
"""

import json
import logging
from typing import List

logger = logging.getLogger(__name__)


# ============================================================
# PHẦN 3A: PROMPT TEMPLATE — SUPER BATCHING
# ============================================================
# THIẾT KẾ PROMPT:
# - Gộp cả Metadata + Comments vào 1 prompt duy nhất
# - Yêu cầu AI trả về nested JSON với 2 phần: phân tích video + phân tích comments
# - Ép buộc cấu trúc JSON cụ thể → đảm bảo parse được, không cần retry

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích nội dung YouTube và mạng xã hội.
Nhiệm vụ: Phân tích ĐỒNG THỜI metadata video và tất cả bình luận của video đối thủ.

QUY TẮC BẮT BUỘC (KHÔNG ĐƯỢC VI PHẠM):
1. Trả lời ĐÚNG bằng JSON object, TUYỆT ĐỐI KHÔNG thêm text/markdown bên ngoài JSON.
2. KHÔNG bọc JSON trong ```json``` hay bất kỳ markdown nào.
3. JSON phải có ĐÚNG 2 keys cấp 1: "phan_tich_video" và "phan_tich_binh_luan".
4. Cấu trúc "phan_tich_video" gồm:
   - "chu_de_chinh": string — chủ đề chính của video
   - "tu_khoa": mảng ĐÚNG 3 từ khóa quan trọng nhất
   - "tom_tat": string — tóm tắt nội dung trong 2-3 câu
   - "danh_gia_tiem_nang": string — đánh giá tiềm năng viral/engagement
5. Cấu trúc "phan_tich_binh_luan" gồm:
   - "comments": mảng các object, MỖI object có đúng 4 keys:
     + "stt": integer — số thứ tự (theo thứ tự input)
     + "noi_dung": string — nội dung gốc từ input
     + "cam_xuc": MỘT TRONG ["Tích cực", "Tiêu cực", "Trung lập"]
     + "y_dinh": MỘT TRONG ["Khen ngợi", "Chê bai", "Hỏi đáp", "Spam"]
   - "tong_ket": object gồm:
     + "tich_cuc": integer — số lượng comments tích cực
     + "tieu_cuc": integer — số lượng comments tiêu cực
     + "trung_lap": integer — số lượng comments trung lập
6. Phân tích bằng tiếng Việt.
7. KHÔNG bỏ sót bình luận nào."""

USER_PROMPT_TEMPLATE = """Phân tích video YouTube đối thủ sau:

══════ METADATA VIDEO ══════
TIÊU ĐỀ: {title}
LƯỢT XEM: {views}
MÔ TẢ: {description}

══════ DANH SÁCH BÌNH LUẬN ({count} bình luận) ══════
{numbered_comments}

══════ YÊU CẦU OUTPUT ══════
Trả về ĐÚNG JSON object với cấu trúc:
{{
  "phan_tich_video": {{
    "chu_de_chinh": "...",
    "tu_khoa": ["keyword1", "keyword2", "keyword3"],
    "tom_tat": "...",
    "danh_gia_tiem_nang": "..."
  }},
  "phan_tich_binh_luan": {{
    "comments": [
      {{"stt": 1, "noi_dung": "...", "cam_xuc": "...", "y_dinh": "..."}},
      ...
    ],
    "tong_ket": {{
      "tich_cuc": 0,
      "tieu_cuc": 0,
      "trung_lap": 0
    }}
  }}
}}"""

# ============================================================
# CẤU HÌNH NVIDIA NIM API
# ============================================================
# GIẢI THÍCH:
# - NVIDIA NIM dùng chuẩn OpenAI-compatible → dùng thư viện openai
# - base_url trỏ tới NVIDIA thay vì OpenAI
# - Model có thể đổi sang bất kỳ model nào trên build.nvidia.com
#   Ví dụ: "meta/llama-3.1-405b-instruct", "google/gemma-2-27b-it",
#          "mistralai/mixtral-8x7b-instruct-v0.1"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"


# ============================================================
# PHẦN 3B: GỌI NVIDIA NIM API VỚI TỐI ƯU CHI PHÍ
# ============================================================

def analyze_with_nvidia(metadata: dict, comments: List[str], api_key: str) -> dict:
    """
    Gọi NVIDIA NIM API phân tích ĐỒNG THỜI metadata + comments (SUPER BATCHING).

    KỸ THUẬT TỐI ƯU:
    1. SUPER BATCHING: Gộp metadata + tất cả comments vào 1 prompt
       → Chỉ tốn 1 lần gọi API thay vì N+1 lần
    2. Temperature = 0.1: Kết quả deterministic, dễ parse JSON
    3. Cắt description dài > 500 ký tự: Tiết kiệm input token

    NVIDIA NIM API:
    - Dùng OpenAI SDK với base_url = https://integrate.api.nvidia.com/v1
    - API key format: nvapi-...
    - Model: meta/llama-3.1-405b-instruct (có thể đổi)

    Args:
        metadata: dict chứa title, views, description đã sạch
        comments: list comments đã sạch
        api_key: NVIDIA API key (nvapi-...)

    Returns:
        dict chứa kết quả phân tích lồng nhau (nested JSON):
        - phan_tich_video: chủ đề, từ khóa, tóm tắt, đánh giá
        - phan_tich_binh_luan: phân loại từng comment + tổng kết

    Raises:
        RuntimeError: Khi API call thất bại hoặc response không parse được
    """
    logger.info("🤖 Gọi NVIDIA NIM API — SUPER BATCHING (1 call duy nhất)...")
    logger.info(f"  📊 Input: metadata + {len(comments)} comments")
    logger.info(f"  🖥️  Model: {NVIDIA_MODEL}")

    # --- Đánh số comments để AI phân biệt ranh giới ---
    # Format: [1] nội dung comment 1
    #         [2] nội dung comment 2
    numbered = "\n".join(
        f"[{i + 1}] {comment}" for i, comment in enumerate(comments)
    )

    # --- Xây dựng prompt ---
    # Cắt description dài > 500 ký tự để TIẾT KIỆM input token
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=metadata.get("title", "N/A"),
        views=metadata.get("views", "N/A"),
        description=metadata.get("description", "")[:500],
        count=len(comments),
        numbered_comments=numbered,
    )

    # ─── PREVIEW: Xem dữ liệu trước khi gửi lên NVIDIA NIM API ───
    print("\n" + "🔶" * 35)
    print("🔍 XEM TRƯỚC DỮ LIỆU GỬI LÊN NVIDIA NIM API")
    print("🔶" * 35)

    # Tóm tắt thống kê
    estimated_tokens = (len(SYSTEM_PROMPT) + len(user_prompt)) // 4  # ~4 chars/token
    print(f"\n┌─── THỐNG KÊ ───")
    print(f"│  🖥️  Model: {NVIDIA_MODEL}")
    print(f"│  📊 Metadata: title={metadata.get('title', 'N/A')[:50]}...")
    print(f"│  👁️  Views: {metadata.get('views', 'N/A')}")
    print(f"│  💬 Số comments: {len(comments)}")
    print(f"│  📝 Ước tính tokens: ~{estimated_tokens:,} tokens")
    print(f"└─── END THỐNG KÊ ───\n")

    print("┌─── SYSTEM PROMPT ───")
    print(SYSTEM_PROMPT)
    print("└─── END SYSTEM PROMPT ───\n")
    print("┌─── USER PROMPT (Dữ liệu thực tế) ───")
    print(user_prompt)
    print("└─── END USER PROMPT ───")
    print("🔶" * 35 + "\n")

    # ─── XÁC NHẬN TRƯỚC KHI GỬI API ───
    confirm = input("❓ Bạn có muốn gửi dữ liệu này lên NVIDIA NIM API? [Y/n]: ").strip().lower()
    if confirm in ("n", "no", "không", "ko"):
        logger.info("⏹️  Người dùng đã HỦY — không gọi API.")
        raise RuntimeError("Người dùng hủy gọi API. Pipeline dừng tại bước AI Analysis.")

    # --- Import và cấu hình OpenAI client cho NVIDIA NIM ---
    from openai import OpenAI

    client = OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
    )

    try:
        # --- Gọi API (1 lần duy nhất!) ---
        # GIẢI THÍCH CÁC THAM SỐ:
        #   - model: Model trên NVIDIA NIM (Llama 3.1 405B)
        #   - temperature=0.1: Output nhất quán, ít "sáng tạo" → dễ parse JSON
        #   - max_tokens=4096: Giới hạn output token
        #   - messages: Gồm system prompt + user prompt (chuẩn OpenAI format)
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=4096,
        )

        # --- Parse JSON response ---
        raw_text = response.choices[0].message.content.strip()

        # Phòng trường hợp AI bọc JSON trong ```json ... ```
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]  # Bỏ dòng đầu (```json)
            raw_text = raw_text.rsplit("```", 1)[0]  # Bỏ dòng cuối (```)
            raw_text = raw_text.strip()

        result = json.loads(raw_text)

        # --- Log kết quả ---
        video_analysis = result.get("phan_tich_video", {})
        comments_analysis = result.get("phan_tich_binh_luan", {})
        logger.info(f"  ✅ Chủ đề: {video_analysis.get('chu_de_chinh', 'N/A')}")
        logger.info(
            f"  ✅ Đã phân tích {len(comments_analysis.get('comments', []))} comments"
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(f"  ❌ Lỗi parse JSON từ NVIDIA NIM: {e}")
        logger.error(f"  📄 Raw response: {raw_text[:200]}...")
        raise RuntimeError(f"NVIDIA NIM trả về JSON không hợp lệ: {e}") from e

    except Exception as e:
        logger.error(f"  ❌ Lỗi gọi NVIDIA NIM API: {e}")
        raise RuntimeError(f"NVIDIA NIM API call thất bại: {e}") from e