from typing import Annotated

from pydantic import AfterValidator, StringConstraints

from app.helpers.text import normalize


def require_searchable_text(search_query: str) -> str:
    # Des diacritiques combinants seuls passent la longueur mais deviennent "" une fois
    # normalisés : la requête correspondrait alors à tout. Le repository normalise déjà.
    if not normalize(search_query):
        raise ValueError("query is empty after normalization")
    # Postgres refuse le caractère nul dans un texte : sans ce contrôle, 500 au lieu de 422.
    if "\x00" in search_query:
        raise ValueError("query contains a null character")
    return search_query


# Le strip passe avant les contrôles de longueur : "   " et " a " donnent 422.
SearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=100),
    AfterValidator(require_searchable_text),
]

# Un seul caractère suffit dans le chat : "g", "?" ou un emoji sont des recherches utiles.
ChatSearchQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    AfterValidator(require_searchable_text),
]
