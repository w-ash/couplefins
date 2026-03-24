from src.infrastructure.auth.password import hash_password, verify_password


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("mysecretpassword")
    assert verify_password("mysecretpassword", hashed) is True


def test_wrong_password_returns_false() -> None:
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_hash_is_not_plaintext() -> None:
    hashed = hash_password("mysecretpassword")
    assert hashed != "mysecretpassword"
    assert hashed.startswith("$argon2")


def test_different_hashes_for_same_password() -> None:
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2  # salted hashes differ
