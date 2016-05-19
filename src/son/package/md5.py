import hashlib
import os


def generate_hash(f, cs=128):
    return __generate_hash__(f, cs) if os.path.isfile(f) else __generate_hash_path__(f, cs)


def __generate_hash__(f, cs=128):
    hash = hashlib.md5()
    with open(f, "rb") as file:
        for chunk in iter(lambda: file.read(cs), b''):
            hash.update(chunk)
    return hash.hexdigest()


def __generate_hash_path__(p, cs=128):
    hash = hashlib.md5()
    for root, dir, files in os.walk(p):
        for f in files:
            hash.update(__generate_hash__(f, cs))
    return hash.hexdigest()

