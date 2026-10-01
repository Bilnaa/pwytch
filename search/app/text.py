import unicodedata


def normalize(text: str) -> str:

    text = text.casefold().strip()
    text = "".join(
        charactere
        for charactere in unicodedata.normalize("NFD", text)
        if unicodedata.category(charactere) != "Mn"
    )
    return text
