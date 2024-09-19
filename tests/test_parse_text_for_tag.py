from textual_guis.utils import parse_text_for_tag


def test_no_tags():
    text = "This is a plain text without any tags."
    result = parse_text_for_tag(text, "p")
    assert result == []

def test_single_tag():
    text = "This is <p>a single tag</p>."
    result = parse_text_for_tag(text, "p")
    assert result == ["a single tag"]

def test_multiple_tags():
    text = "This is <p>the first tag</p> and <p>the second tag</p>."
    result = parse_text_for_tag(text, "p")
    assert result == ["the first tag", "the second tag"]

def test_nested_tags():
    text = "This is <p>an outer tag <p>with a nested tag</p></p>."
    result = parse_text_for_tag(text, "p")
    assert result == ["an outer tag <p>with a nested tag</p>"]

def test_unclosed_tag():
    text = "This is <p>an unclosed tag."
    result = parse_text_for_tag(text, "p")
    assert result == []

def test_empty_tag():
    text = "This is <p></p>."
    result = parse_text_for_tag(text, "p")
    assert result == [""]
