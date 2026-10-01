# common

Bibliothèque partagée entre les services : les contrats que plusieurs services doivent écrire et lire de la même façon. Aucun service n'importe le code d'un autre service ; seul `common` est partagé.

## Contenu

| Module               | Contenu                                                                     |
|----------------------|-----------------------------------------------------------------------------|
| `common.topics`      | Noms des topics MQTT (`STREAM_STARTED = "stream/started"`, …)               |
| `common.events`      | Modèles Pydantic des events : `BaseEvent`, `StreamStarted`, `StreamEnded`   |
| `common.pagination`  | `Page[T]` : réponse paginée (`items`, `total`, `page`, `size`)              |

Exemple :

```python
from common.events import StreamStarted
from common.topics import STREAM_STARTED

payload = StreamStarted(...).model_dump_json()          # côté producteur
event = StreamStarted.model_validate_json(payload)      # côté consommateur
```

## Règles d'équipe

- `common` ne contient aucune logique métier propre à un service.
- Toute modification de `common` est annoncée à l'équipe **avant** le merge : un changement de modèle ou de topic casse les services qui l'utilisent.

## Ajouter `common` à un service

Dans le `pyproject.toml` du service :

```toml
[project]
dependencies = [
    "common",
]

[tool.uv.sources]
common = { path = "../common", editable = true }
```

Puis `uv sync`. En mode éditable, une modification de `common` est visible tout de suite, sans réinstaller.

## Test

    cd common
    uv run pytest
