"""
Test cho analyzer.py — Kiểm tra prompt building + JSON parsing.
KHÔNG gọi API thật — dùng mock data để test offline.

Chạy: python test_analyzer.py
      hoặc: python -m pytest test_analyzer.py -v
"""

import json
import logging
from analyzer import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

# Tắt logging khi test
logging.disable(logging.CRITICAL)

# ============================================================
# DỮ LIỆU MẪU (Mock data từ scraper + cleaner)
# ============================================================

MOCK_METADATA = {
    "title": "CEO Dat Bike: Cuộc đời phải rực rỡ | VnExpress",
    "views": "17.742",
    "description": "Bỏ big tech để đi tìm 0,001% khả năng rực rỡ với startup",
}

MOCK_COMMENTS = [
    "Theo dõi hành trình của Dat Bike từ đầu mới thấy Sơn rất kiên định",
    "Thị trường khởi nghiệp hiện nay thì Dat Bike là một cái tên rất sáng",
    "Xe điện là phải thế này mới cạnh tranh đường dài với xe máy xăng",
    "Anh Sơn này có hoài bão lớn, chúc anh thành công",
    "Quan trọng là chất lượng và giá cả",
]

# ============================================================
# MOCK GEMINI RESPONSE (Giả lập kết quả Gemini trả về)
# ============================================================

MOCK_GEMINI_RESPONSE = {
    "phan_tich_video": {
        "chu_de_chinh": "Khởi nghiệp xe máy điện Dat Bike",
        "tu_khoa": ["Dat Bike", "startup", "xe điện"],
        "tom_tat": "Video kể câu chuyện của CEO Dat Bike về hành trình khởi nghiệp xe máy điện.",
        "danh_gia_tiem_nang": "Tiềm năng engagement cao nhờ nội dung truyền cảm hứng."
    },
    "phan_tich_binh_luan": {
        "comments": [
            {"stt": 1, "noi_dung": "Theo dõi hành trình...", "cam_xuc": "Tích cực", "y_dinh": "Khen ngợi"},
            {"stt": 2, "noi_dung": "Thị trường khởi nghiệp...", "cam_xuc": "Tích cực", "y_dinh": "Khen ngợi"},
            {"stt": 3, "noi_dung": "Xe điện là phải...", "cam_xuc": "Tích cực", "y_dinh": "Khen ngợi"},
            {"stt": 4, "noi_dung": "Anh Sơn này...", "cam_xuc": "Tích cực", "y_dinh": "Khen ngợi"},
            {"stt": 5, "noi_dung": "Quan trọng là...", "cam_xuc": "Trung lập", "y_dinh": "Khen ngợi"},
        ],
        "tong_ket": {
            "tich_cuc": 4,
            "tieu_cuc": 0,
            "trung_lap": 1,
        }
    }
}


# ============================================================
# TEST 1: SYSTEM PROMPT — Kiểm tra cấu trúc
# ============================================================

def test_system_prompt_contains_required_keys():
    """System prompt phải đề cập đúng các keys JSON yêu cầu."""
    assert "phan_tich_video" in SYSTEM_PROMPT
    assert "phan_tich_binh_luan" in SYSTEM_PROMPT
    assert "chu_de_chinh" in SYSTEM_PROMPT
    assert "tu_khoa" in SYSTEM_PROMPT
    assert "cam_xuc" in SYSTEM_PROMPT
    assert "y_dinh" in SYSTEM_PROMPT
    assert "tong_ket" in SYSTEM_PROMPT
    print("✅ test_system_prompt_contains_required_keys — PASSED")


def test_system_prompt_sentiment_values():
    """System prompt phải liệt kê đúng 3 giá trị cảm xúc."""
    assert "Tích cực" in SYSTEM_PROMPT
    assert "Tiêu cực" in SYSTEM_PROMPT
    assert "Trung lập" in SYSTEM_PROMPT
    print("✅ test_system_prompt_sentiment_values — PASSED")


def test_system_prompt_intent_values():
    """System prompt phải liệt kê đúng 4 giá trị ý định."""
    assert "Khen ngợi" in SYSTEM_PROMPT
    assert "Chê bai" in SYSTEM_PROMPT
    assert "Hỏi đáp" in SYSTEM_PROMPT
    assert "Spam" in SYSTEM_PROMPT
    print("✅ test_system_prompt_intent_values — PASSED")


def test_system_prompt_forces_json():
    """System prompt phải yêu cầu trả JSON, không markdown."""
    assert "JSON" in SYSTEM_PROMPT
    assert "KHÔNG" in SYSTEM_PROMPT  # KHÔNG thêm text bên ngoài
    print("✅ test_system_prompt_forces_json — PASSED")


# ============================================================
# TEST 2: USER PROMPT TEMPLATE — Kiểm tra format
# ============================================================

def test_user_prompt_template_placeholders():
    """Template phải có đủ các placeholder."""
    assert "{title}" in USER_PROMPT_TEMPLATE
    assert "{views}" in USER_PROMPT_TEMPLATE
    assert "{description}" in USER_PROMPT_TEMPLATE
    assert "{count}" in USER_PROMPT_TEMPLATE
    assert "{numbered_comments}" in USER_PROMPT_TEMPLATE
    print("✅ test_user_prompt_template_placeholders — PASSED")


def test_user_prompt_renders_correctly():
    """Test render template với data thật."""
    numbered = "\n".join(
        f"[{i+1}] {c}" for i, c in enumerate(MOCK_COMMENTS)
    )
    prompt = USER_PROMPT_TEMPLATE.format(
        title=MOCK_METADATA["title"],
        views=MOCK_METADATA["views"],
        description=MOCK_METADATA["description"][:500],
        count=len(MOCK_COMMENTS),
        numbered_comments=numbered,
    )

    # Kiểm tra data được nhúng đúng
    assert MOCK_METADATA["title"] in prompt
    assert MOCK_METADATA["views"] in prompt
    assert "5 bình luận" in prompt
    assert "[1]" in prompt
    assert "[5]" in prompt
    assert MOCK_COMMENTS[0] in prompt
    assert MOCK_COMMENTS[-1] in prompt

    print("✅ test_user_prompt_renders_correctly — PASSED")


def test_user_prompt_description_truncated():
    """Test description dài bị cắt 500 ký tự."""
    long_desc = "A" * 1000
    numbered = "[1] test comment"
    prompt = USER_PROMPT_TEMPLATE.format(
        title="Test",
        views="100",
        description=long_desc[:500],
        count=1,
        numbered_comments=numbered,
    )
    # Description trong prompt chỉ có 500 ký tự 'A'
    assert "A" * 500 in prompt
    assert "A" * 501 not in prompt
    print("✅ test_user_prompt_description_truncated — PASSED")


# ============================================================
# TEST 3: MOCK RESPONSE — Kiểm tra cấu trúc JSON Gemini
# ============================================================

def test_mock_response_structure():
    """Response phải có đúng 2 keys cấp 1."""
    assert "phan_tich_video" in MOCK_GEMINI_RESPONSE
    assert "phan_tich_binh_luan" in MOCK_GEMINI_RESPONSE
    assert len(MOCK_GEMINI_RESPONSE) == 2
    print("✅ test_mock_response_structure — PASSED")


def test_mock_response_video_analysis():
    """Phân tích video phải có đủ 4 fields."""
    video = MOCK_GEMINI_RESPONSE["phan_tich_video"]
    assert "chu_de_chinh" in video
    assert "tu_khoa" in video
    assert "tom_tat" in video
    assert "danh_gia_tiem_nang" in video
    assert len(video["tu_khoa"]) == 3
    print("✅ test_mock_response_video_analysis — PASSED")


def test_mock_response_comments_analysis():
    """Phân tích bình luận phải có đúng format."""
    bl = MOCK_GEMINI_RESPONSE["phan_tich_binh_luan"]
    assert "comments" in bl
    assert "tong_ket" in bl

    # Mỗi comment phải có 4 keys
    for c in bl["comments"]:
        assert "stt" in c
        assert "noi_dung" in c
        assert "cam_xuc" in c
        assert "y_dinh" in c
        assert c["cam_xuc"] in ["Tích cực", "Tiêu cực", "Trung lập"]
        assert c["y_dinh"] in ["Khen ngợi", "Chê bai", "Hỏi đáp", "Spam"]

    print("✅ test_mock_response_comments_analysis — PASSED")


def test_mock_response_tong_ket_math():
    """Tổng kết số lượng phải khớp với danh sách comments."""
    bl = MOCK_GEMINI_RESPONSE["phan_tich_binh_luan"]
    total = bl["tong_ket"]["tich_cuc"] + bl["tong_ket"]["tieu_cuc"] + bl["tong_ket"]["trung_lap"]
    assert total == len(bl["comments"])
    print("✅ test_mock_response_tong_ket_math — PASSED")


def test_mock_response_serializable():
    """Response phải serialize/deserialize JSON thành công."""
    json_str = json.dumps(MOCK_GEMINI_RESPONSE, ensure_ascii=False)
    parsed = json.loads(json_str)
    assert parsed == MOCK_GEMINI_RESPONSE
    print("✅ test_mock_response_serializable — PASSED")


# ============================================================
# TEST 4: JSON CLEANUP — Test xử lý markdown wrapper
# ============================================================

def test_json_cleanup_markdown_wrapper():
    """Test xử lý khi Gemini bọc JSON trong ```json```."""
    raw = '```json\n{"key": "value"}\n```'
    # Logic từ analyzer.py
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
    result = json.loads(raw)
    assert result == {"key": "value"}
    print("✅ test_json_cleanup_markdown_wrapper — PASSED")


def test_json_cleanup_no_wrapper():
    """Test khi Gemini trả JSON thuần (không bọc markdown)."""
    raw = '{"phan_tich_video": {}, "phan_tich_binh_luan": {}}'
    result = json.loads(raw.strip())
    assert "phan_tich_video" in result
    print("✅ test_json_cleanup_no_wrapper — PASSED")


# ============================================================
# CHẠY TẤT CẢ TESTS
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 CHẠY TEST CHO analyzer.py")
    print("=" * 50)

    tests = [
        test_system_prompt_contains_required_keys,
        test_system_prompt_sentiment_values,
        test_system_prompt_intent_values,
        test_system_prompt_forces_json,
        test_user_prompt_template_placeholders,
        test_user_prompt_renders_correctly,
        test_user_prompt_description_truncated,
        test_mock_response_structure,
        test_mock_response_video_analysis,
        test_mock_response_comments_analysis,
        test_mock_response_tong_ket_math,
        test_mock_response_serializable,
        test_json_cleanup_markdown_wrapper,
        test_json_cleanup_no_wrapper,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} — FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} — ERROR: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"📊 Kết quả: {passed}/{passed + failed} tests passed")
    if failed == 0:
        print("🎉 TẤT CẢ TESTS ĐỀU PASSED!")
    else:
        print(f"⚠️ {failed} tests FAILED!")
    print("=" * 50)
