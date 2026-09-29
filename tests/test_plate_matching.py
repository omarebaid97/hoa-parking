from app.plate_utils import normalize_plate, plate_match_key


def test_normalize_strips_spaces_and_dashes_and_uppercases():
    assert normalize_plate("abc-1234") == "ABC1234"
    assert normalize_plate("  abc 1234 ") == "ABC1234"
    assert normalize_plate("abc--12 34") == "ABC1234"


def test_match_key_folds_o_and_0():
    assert plate_match_key("ABO123") == plate_match_key("AB0123")


def test_match_key_folds_i_and_1():
    assert plate_match_key("AB1123") == plate_match_key("ABI123")


def test_match_key_is_case_and_format_insensitive():
    assert plate_match_key("abc-1234") == plate_match_key("ABC 1234")


def test_different_plates_do_not_match():
    assert plate_match_key("ABC1234") != plate_match_key("ABC1235")
