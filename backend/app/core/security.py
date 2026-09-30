from argon2 import PasswordHasher

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)
