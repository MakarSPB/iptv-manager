import random
import string

def generate_short_id(length: int = 5) -> str:
    return ''.join(random.choices(string.ascii_lowercase, k=length))