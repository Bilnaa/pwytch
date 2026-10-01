# common

Seul package importable directement par les microservices (`from common import ...`). Il contient ce que plusieurs services partagent, jamais de logique métier propre à un seul.

## Règle d'équipe

**Toute modification de `common` est annoncée à l'équipe avant d'être mergée** : elle touche tous les services. Les modèles d'events sont versionnés (`version`) : changer un champ casse les consommateurs.

## Contenu

| Module          | Contenu |
|-----------------|---------|
| `common.topics` | Les constantes des topics MQTT (`STREAM_STARTED`, `STREAM_ENDED`, `CHAT_MESSAGE`, `SEARCH_HIT`, `BOOKMARK_DELETED`, `PLAYER_EVENT`) |
| `common.events` | Les modèles Pydantic des events. Tous héritent de `BaseEvent` (`event_id`, `version`) |
| `common.mqtt`   | `MqttClient` : client asynchrone avec reconnexion, `publish` et `subscribe` |

À venir : `common.errors`, `common.pagination`, `common.identity`.

## Events

Les champs suivent la carte des topics de #11.

| Topic | Modèle | Champs |
|---|---|---|
| `stream/started` | `StreamStarted` | `stream_id`, `streamer_id`, `streamer_name`, `title`, `game`, `started_at` |
| `stream/ended` | `StreamEnded` | `stream_id`, `streamer_id`, `ended_at`, `duration_s`, `reason` (`normal` ou `error`) |
| `chat/message` | `ChatMessage` | `message_id`, `stream_id`, `author_id`, `author_name`, `content`, `sent_at` |
| `search/hit` | `SearchHit` | `item_type` (`streamer` ou `message`), `item_id`, `query`, `hit_at` |
| `bookmarks/deleted` | `BookmarkDeleted` | `bookmark_id`, `user_id`, `target_type`, `target_id`, `deleted_at` |
| `player/event` | `PlayerEvent` | `stream_id`, `event_type` (`play`, `pause` ou `stop`), `user_id` (peut être `null`), `occurred_at` |

`event_id` (UUID) est généré à la création de l'event. Il sert à dédupliquer : avec la QoS 1, un message peut arriver deux fois.

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

## Tester

    cd common
    uv run pytest
