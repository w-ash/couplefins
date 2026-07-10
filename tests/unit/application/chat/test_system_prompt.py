from datetime import date

from src.application.chat.system_prompt import build_system_prompt
from tests.fixtures.factories import make_person


def test_includes_person_names() -> None:
    alice = make_person(name="Alice")
    bob = make_person(name="Bob")
    blocks = build_system_prompt(alice, bob, date(2026, 3, 15), ["Food & Dining"])

    text = blocks[0]["text"]
    assert "Alice" in text
    assert "Bob" in text


def test_domain_primer_matches_spotted_semantics() -> None:
    """Spotted is the beneficiary's PERSONAL spending (docs/domain.md).

    A primer that claims household=true here steers the model into proposing
    budget-corrupting mutations — pin the two load-bearing facts.
    """
    blocks = build_system_prompt(
        make_person(name="A"),
        make_person(name="B"),
        date(2026, 3, 15),
        [],
    )
    text = blocks[0]["text"]
    assert "Spotted: household=false" in text
    assert "person-name tags do NOT set it" in text


def test_includes_current_date() -> None:
    blocks = build_system_prompt(
        make_person(name="A"),
        make_person(name="B"),
        date(2026, 3, 15),
        [],
    )
    assert "2026-03-15" in blocks[0]["text"]


def test_includes_category_groups() -> None:
    groups = ["Food & Dining", "Travel", "Home Expenses"]
    blocks = build_system_prompt(
        make_person(name="A"),
        make_person(name="B"),
        date(2026, 1, 1),
        groups,
    )
    text = blocks[0]["text"]
    for group in groups:
        assert group in text


def test_empty_groups_shows_placeholder() -> None:
    blocks = build_system_prompt(
        make_person(name="A"),
        make_person(name="B"),
        date(2026, 1, 1),
        [],
    )
    assert "(none configured)" in blocks[0]["text"]


def test_last_block_has_cache_control() -> None:
    blocks = build_system_prompt(
        make_person(name="A"),
        make_person(name="B"),
        date(2026, 1, 1),
        ["Food"],
    )
    last = blocks[-1]
    assert last["cache_control"] == {"type": "ephemeral"}


def test_no_user_generated_content_in_prompt() -> None:
    """Merchant names, transaction notes, etc. must not appear in the prompt."""
    blocks = build_system_prompt(
        make_person(name="Alice"),
        make_person(name="Bob"),
        date(2026, 1, 1),
        ["Food & Dining"],
    )
    text = blocks[0]["text"]
    assert "Whole Foods" not in text
    assert "Uber Eats" not in text


def test_uses_xml_structure() -> None:
    blocks = build_system_prompt(
        make_person(name="Alice"),
        make_person(name="Bob"),
        date(2026, 1, 1),
        ["Food & Dining"],
    )
    text = blocks[0]["text"]
    assert "<identity>" in text
    assert "<domain_model>" in text
    assert "<response_format>" in text


def test_fiona_voice_includes_examples_and_rules() -> None:
    blocks = build_system_prompt(
        make_person(name="Alice", chat_voice="fiona"),
        make_person(name="Bob"),
        date(2026, 1, 1),
        ["Food & Dining"],
    )
    text = blocks[0]["text"]
    assert "<voice_examples>" in text
    assert "</voice_examples>" in text
    assert "<voice_rules>" in text
    assert "</voice_rules>" in text
    assert "hun" in text.lower()
    assert "plain language" in text.lower()


def test_standard_voice_omits_examples_and_rules() -> None:
    blocks = build_system_prompt(
        make_person(name="Alice", chat_voice="standard"),
        make_person(name="Bob"),
        date(2026, 1, 1),
        ["Food & Dining"],
    )
    text = blocks[0]["text"]
    assert "<voice_examples>" not in text
    assert "<voice_rules>" not in text


def test_invalid_voice_falls_back_to_standard() -> None:
    blocks = build_system_prompt(
        make_person(name="Alice", chat_voice="nonexistent"),
        make_person(name="Bob"),
        date(2026, 1, 1),
        ["Food & Dining"],
    )
    text = blocks[0]["text"]
    assert "financial assistant for Couplefins" in text
    assert "<voice_examples>" not in text


def test_response_format_uses_positive_framing() -> None:
    """Format instructions should say what to do, not what not to do."""
    blocks = build_system_prompt(
        make_person(name="Alice"),
        make_person(name="Bob"),
        date(2026, 1, 1),
        ["Food & Dining"],
    )
    text = blocks[0]["text"]
    # Positive framing: "Write as plain text", "Use $"
    assert "plain text" in text
    assert "$" in text
    # Should not contain negative emoji prohibition
    assert "never use emoji" not in text.lower()
    assert "don't use emoji" not in text.lower()
