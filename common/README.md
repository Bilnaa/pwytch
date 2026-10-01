# common

Bibliothèque partagée entre les services : les contrats que plusieurs services doivent écrire et lire de la même façon. Aucun service n'importe le code d'un autre service ; seul `common` est partagé.

## Contenu

| Module               | Contenu                                                                     |
|----------------------|-----------------------------------------------------------------------------|
| `common.topics`      | Noms des topics MQTT (`STREAM_STARTED = "stream/started"`, …)               |
| `common.events`      | Modèles Pydantic des events : `BaseEvent`, `StreamStarted`, `StreamEnded`, `PlayerEvent` |
| `common.mqtt`        | `MqttClient` : client asynchrone avec reconnexion, `publish` et `subscribe` |
| `common.pagination`  | `Page[T]` : réponse paginée (`items`, `total`, `page`, `size`)              |

Exemple :

```python
from common.events import StreamStarted
from common.topics import STREAM_STARTED

payload = StreamStarted(...).model_dump_json()          # côté producteur
event = StreamStarted.model_validate_json(payload)      # côté consommateur
```

`event_id` (UUID) est généré à la création de l'event si on ne le donne pas. Il sert à dédupliquer : avec la QoS 1, un message peut arriver deux fois.

## Client MQTT

```python
from common import topics
from common.events import StreamEnded
from common.mqtt import MqttClient

mqtt = MqttClient(host="localhost", port=1883, client_id="main")

async def on_ended(event: StreamEnded) -> None:
    ...

mqtt.subscribe(topics.STREAM_ENDED, StreamEnded, on_ended)
await mqtt.start()   # au démarrage du service, en tâche de fond
await mqtt.publish(topics.STREAM_STARTED, event)
await mqtt.stop()    # à l'arrêt
```

- Tout passe en QoS 1
- La connexion est rétablie toute seule (`reconnect_seconds`, 5 s par défaut) et les abonnements sont renvoyés au broker
- `publish` lève `NotConnectedError` si le broker est injoignable : à l'appelant de décider (journaliser et continuer, par exemple)
- Un message invalide est ignoré et journalisé, une erreur dans un handler aussi : le consommateur ne plante pas
- Un event dont l'`event_id` a déjà été vu est ignoré (les 1000 derniers sont gardés en mémoire)

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
