LIMIT_INTEGER = 2**31 -1


def get_item_id(key: str) -> str:
    return key.split(":", 1)[1]


def get_item_type(key: str) -> str:
    return key.split(":")[0]
