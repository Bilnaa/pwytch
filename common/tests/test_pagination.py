from pydantic import BaseModel

from common.pagination import Page


class SampleItem(BaseModel):
    name: str


def test_page_of_integers_dumps_all_keys():
    page = Page[int](items=[1, 2], total=5, page=1, size=2)

    assert page.model_dump() == {"items": [1, 2], "total": 5, "page": 1, "size": 2}


def test_page_of_models_serializes_items_as_dicts():
    page = Page[SampleItem](
        items=[SampleItem(name="Zerator")], total=1, page=1, size=20
    )

    assert page.model_dump()["items"] == [{"name": "Zerator"}]


def test_empty_page_is_valid():
    page = Page[SampleItem](items=[], total=0, page=1, size=20)

    assert page.items == []
    assert page.total == 0
