import random
from datetime import datetime
from string import ascii_lowercase


def date_id():
    now = datetime.utcnow()
    return now.strftime("%Y%m%d%H%M%S") + "".join(random.choices(ascii_lowercase, k=6))
