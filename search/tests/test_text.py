import pytest
from app.text import normalize


@pytest.mark.parametrize(
    "input_text, expected_output",
    [
        ("CeLeStE", "celeste"),
        ("Célèste", "celeste"),
        ("Ça Noël", "ca noel"),
        (" gg ", "gg"),
        ("dark souls", "dark souls"),
        ("", ""),
        ("FIFA 26 | any%", "fifa 26 | any%"),
        ("İ", "i"),
        ("Straße", "strasse"),
    ],
)
def test_normalize(input_text, expected_output):
    assert normalize(input_text) == expected_output
