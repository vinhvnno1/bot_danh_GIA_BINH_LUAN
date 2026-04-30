"""
Test cho cleaner.py — Kiểm tra toàn bộ pipeline làm sạch dữ liệu.

Chạy: python test_cleaner.py
      hoặc: python -m pytest test_cleaner.py -v
"""

import logging
from cleaner import clean_metadata, clean_comments, _clean_single_comment, _remove_emojis, _normalize_teencode

# Tắt logging khi test (tránh output rối)
logging.disable(logging.CRITICAL)


# ============================================================
# TEST 1: clean_metadata — Làm sạch metadata video
# ============================================================

def test_clean_metadata_basic():
    """Test cơ bản: xóa HTML, URL, chuẩn hóa views."""
    result = clean_metadata(
        title="🔥 Video siêu hay 🎬 EP 1",
        views="1.245.678 lượt xem",
        description='<p>Mô tả video</p> link: https://example.com liên hệ: test@gmail.com'
    )
    # Title phải xóa emoji
    assert "🔥" not in result["title"]
    assert "🎬" not in result["title"]
    assert "Video siêu hay" in result["title"]

    # Views chỉ giữ số
    assert result["views"] == "1.245.678"

    # Description phải xóa HTML, URL, email
    assert "<p>" not in result["description"]
    assert "https://" not in result["description"]
    assert "@gmail.com" not in result["description"]
    assert "Mô tả video" in result["description"]

    print("✅ test_clean_metadata_basic — PASSED")


def test_clean_metadata_empty():
    """Test edge case: input rỗng."""
    result = clean_metadata(title="", views="", description="")
    assert result["title"] == ""
    assert result["views"] == "N/A"
    assert result["description"] == ""
    print("✅ test_clean_metadata_empty — PASSED")


def test_clean_metadata_views_formats():
    """Test nhiều format views khác nhau."""
    # Format dấu chấm (Việt Nam)
    r1 = clean_metadata("Test", "17.742 lượt xem", "desc")
    assert r1["views"] == "17.742"

    # Format dấu phẩy (US)
    r2 = clean_metadata("Test", "1,245,678 views", "desc")
    assert r2["views"] == "1.245.678"

    # Chỉ có số
    r3 = clean_metadata("Test", "999", "desc")
    assert r3["views"] == "999"

    print("✅ test_clean_metadata_views_formats — PASSED")


# ============================================================
# TEST 2: _remove_emojis — Xóa emoji
# ============================================================

def test_remove_emojis():
    """Test xóa các loại emoji khác nhau."""
    assert _remove_emojis("Hello 😀🔥🎬") == "Hello "
    assert _remove_emojis("Không có emoji") == "Không có emoji"
    assert _remove_emojis("🇻🇳 Việt Nam") == " Việt Nam"
    assert _remove_emojis("") == ""
    print("✅ test_remove_emojis — PASSED")


# ============================================================
# TEST 3: _normalize_teencode — Chuẩn hóa teencode
# ============================================================

def test_normalize_teencode():
    """Test chuẩn hóa teencode tiếng Việt."""
    # Teencode cơ bản
    assert "không" in _normalize_teencode("ko biết").lower()
    assert "được" in _normalize_teencode("dc rồi").lower()
    assert "mình" in _normalize_teencode("mk thích").lower()

    # Teencode nhiều từ
    result = _normalize_teencode("ko dc bn ơi")
    assert "không" in result.lower()
    assert "được" in result.lower()
    assert "bạn" in result.lower()

    # Không nên thay teencode trong từ dài (word boundary)
    original = "không"
    assert _normalize_teencode(original) == original

    print("✅ test_normalize_teencode — PASSED")


# ============================================================
# TEST 4: _clean_single_comment — Làm sạch 1 comment
# ============================================================

def test_clean_single_comment_urls():
    """Test xóa URL khỏi comment."""
    result = _clean_single_comment("Xem thêm tại https://spam.com nha")
    assert "https://" not in result
    assert "spam.com" not in result
    assert "Xem thêm tại" in result

    result2 = _clean_single_comment("Click www.scam.vn để nhận quà")
    assert "www." not in result2

    result3 = _clean_single_comment("Link: bit.ly/abc123")
    assert "bit.ly" not in result3

    print("✅ test_clean_single_comment_urls — PASSED")


def test_clean_single_comment_special_chars():
    """Test gộp ký tự đặc biệt lặp."""
    assert "!" in _clean_single_comment("Hay quá!!!!!!")
    # Chỉ còn 1 dấu !
    cleaned = _clean_single_comment("Hay quá!!!!!!")
    assert "!!" not in cleaned

    cleaned2 = _clean_single_comment("Thật sao???")
    assert "??" not in cleaned2

    print("✅ test_clean_single_comment_special_chars — PASSED")


def test_clean_single_comment_whitespace():
    """Test gộp khoảng trắng thừa."""
    result = _clean_single_comment("  Nhiều    khoảng   trắng  ")
    assert "  " not in result
    assert result == result.strip()
    print("✅ test_clean_single_comment_whitespace — PASSED")


# ============================================================
# TEST 5: clean_comments — Pipeline làm sạch toàn bộ
# ============================================================

def test_clean_comments_basic():
    """Test pipeline đầy đủ."""
    raw = [
        "Video rất hay 🔥🔥🔥",
        "Xem thêm tại https://spam.com !!!",
        "Nội dung chất lượng",
        "",           # Rỗng → bị loại
        "ab",         # Quá ngắn → bị loại
        "Nội dung chất lượng",  # Trùng lặp → bị loại
    ]
    cleaned = clean_comments(raw)

    assert len(cleaned) == 3  # 3 comments hợp lệ, không trùng
    assert "" not in cleaned
    assert "ab" not in cleaned

    print("✅ test_clean_comments_basic — PASSED")


def test_clean_comments_preserves_order():
    """Test giữ nguyên thứ tự comments."""
    raw = ["Bình luận thứ ba", "Bình luận thứ nhất", "Bình luận thứ hai"]
    cleaned = clean_comments(raw)
    assert cleaned[0] == "Bình luận thứ ba"
    assert cleaned[1] == "Bình luận thứ nhất"
    assert cleaned[2] == "Bình luận thứ hai"
    print("✅ test_clean_comments_preserves_order — PASSED")


def test_clean_comments_dedup_after_clean():
    """Test 2 comments khác nhau nhưng giống nhau SAU KHI clean."""
    raw = [
        "ko dc 😭",     # → "không được"
        "Ko dc",         # → "không được" (trùng sau clean)
    ]
    cleaned = clean_comments(raw)
    # Sau clean, 2 comment này nên giống nhau → chỉ giữ 1
    assert len(cleaned) == 1
    print("✅ test_clean_comments_dedup_after_clean — PASSED")


def test_clean_comments_empty_list():
    """Test input rỗng."""
    assert clean_comments([]) == []
    print("✅ test_clean_comments_empty_list — PASSED")


def test_clean_comments_all_spam():
    """Test tất cả comments đều là spam/rỗng."""
    raw = ["", "  ", "ab", "🔥"]
    cleaned = clean_comments(raw)
    assert len(cleaned) == 0
    print("✅ test_clean_comments_all_spam — PASSED")


# ============================================================
# CHẠY TẤT CẢ TESTS
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 CHẠY TEST CHO cleaner.py")
    print("=" * 50)

    tests = [
        test_clean_metadata_basic,
        test_clean_metadata_empty,
        test_clean_metadata_views_formats,
        test_remove_emojis,
        test_normalize_teencode,
        test_clean_single_comment_urls,
        test_clean_single_comment_special_chars,
        test_clean_single_comment_whitespace,
        test_clean_comments_basic,
        test_clean_comments_preserves_order,
        test_clean_comments_dedup_after_clean,
        test_clean_comments_empty_list,
        test_clean_comments_all_spam,
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
