# common

Bibliothèque partagée entre les services : les contrats que plusieurs services doivent écrire et lire de la même façon. Aucun service n'importe le code d'un autre service ; seul `common` est partagé.

## Contenu

| Module               | Contenu                                                                     |
|----------------------|-----------------------------------------------------------------------------|
| `common.topics`      | Noms des topics MQTT (`STREAM_STARTED = "stream/started"`, …)               |
| `common.events`      | Modèles Pydantic des events : `BaseEvent`, `StreamStarted`, `StreamEnded`, `PlayerEvent`, `ChatMessage`, `SearchHit`, `ItemType` |
| `common.mqtt`        | `MqttClient` : client asynchrone avec reconnexion, `publish` et `subscribe` |
| `common.pagination`  | `Page[T]` : réponse paginée (`items`, `total`, `page`, `size`)              |
| `common.identity`    | `UserIdentity`, `to_headers` et la dépendance FastAPI `CurrentUser`         |
| `common.errors`      | `register_internal_error_handler` : toute exception non prévue renvoie un 500 en JSON |

Exemple :

```python
from common.events import StreamStarted
from common.topics import STREAM_STARTED

payload = StreamStarted(...).model_dump_json()          # côté producteur
event = StreamStarted.model_validate_json(payload)      # côté consommateur
```

`event_id` (UUID) est généré à la création de l'event si on ne le donne pas. Il sert à dédupliquer : avec la QoS 1, un message peut arriver deux fois.

`ChatMessage` (topic `chat/message`) :

- publié par `live-chat`, consommé par `search` et `stats` ;
- `message_id` : uuid4 généré par `live-chat`, unique dans tout le système (pas par live) ;
- `content` : `strip`, puis entre 1 et 500 caractères, sinon `ValidationError` ;
- `author_name` : non vide ;
- `sent_at` : date avec fuseau obligatoire (UTC conseillé), une date sans fuseau est refusée.

`SearchHit` (topic `search/hit`) :

- publié par `search`, consommé par `stats` ; un event par élément renvoyé par une recherche ;
- `item_type` : `ItemType`, un `StrEnum` (`"streamer"` ou `"message"`). Contrairement aux autres champs à valeurs fixes, il s'importe (`from common.events import ItemType`) pour typer les routes de `stats` ;
- `item_id` : identifiant en texte, `"42"` pour un streamer, l'UUID du message pour un message ;
- `query` : le `q` tapé, après `strip`, non normalisé ;
- `hit_at` : date avec fuseau obligatoire, instant de la recherche (même valeur pour tous les events d'une recherche).

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
- Avec un `client_id`, la session est persistante (`clean_session=False`) : le broker garde les messages reçus pendant que le service est déconnecté ou redémarre, et les envoie à la reconnexion. Le `client_id` doit donc être unique par service
  - La session ne survit pas à un redémarrage du broker : Mosquitto tourne sans `persistence true`, les sessions et les messages en attente sont en mémoire
  - Le message est acquitté (PUBACK) dès sa réception, avant que le handler ne tourne : si le service plante pendant le traitement, ce message est perdu
- `publish` lève `NotConnectedError` si le broker est injoignable : à l'appelant de décider (journaliser et continuer, par exemple)
- Un message invalide est ignoré et journalisé, une erreur dans un handler aussi : le consommateur ne plante pas
- Un event dont l'`event_id` a déjà été traité avec succès est ignoré (les 1000 derniers sont gardés en mémoire). Un event dont le handler a échoué n'est pas marqué : s'il est renvoyé, il est traité de nouveau

## Identité de l'utilisateur

Les satellites ne gèrent pas l'authentification : `main` authentifie l'utilisateur et le transmet dans les headers `X-User-Id`, `X-User-Name` et `X-User-Role`.

```python
from common.identity import CurrentUser, UserIdentity, to_headers

# côté main : ajouter l'utilisateur aux requêtes vers un satellite
headers = to_headers(UserIdentity(id=user.id, name=user.username, role=user.role))

# côté satellite : lire l'utilisateur dans les headers
@router.get("/me")
def read_me(user: CurrentUser) -> UserIdentity:
    return user
```

- Si un header manque, si `X-User-Id` n'est pas un entier entre 1 et 2 147 483 647 (`42.0`, `+42`, `0`, `-1` ou `2147483648` sont refusés) ou si `X-User-Name` ou `X-User-Role` est vide, la dépendance renvoie 401
- Un satellite fait confiance à ces headers : il ne doit être joignable qu'à travers `main`, sinon n'importe qui peut se faire passer pour un autre utilisateur

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
