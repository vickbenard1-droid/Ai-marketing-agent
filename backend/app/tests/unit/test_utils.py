from app.core.utils import slugify


def test_slugify_basic():
    assert slugify("Acme Marketing Co.") == "acme-marketing-co"


def test_slugify_collapses_repeated_separators():
    assert slugify("Acme   &&&  Co") == "acme-co"


def test_slugify_strips_leading_trailing_separators():
    assert slugify("---Acme---") == "acme"


def test_slugify_falls_back_for_no_alphanumeric_input():
    result = slugify("!!!")
    assert result != ""
    assert "-" not in result or len(result) == 8  # short random fallback id
