from apps.api.routers.auth import hash_password, verify_password


def test_password_hashing_and_verification():
    password = "My$ecureP@ssw0rd"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)
