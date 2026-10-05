# stats

Compteurs globaux de la plateforme. `stats` écoute les events MQTT des autres services et tient un compteur par élément : combien de fois un élément a été trouvé par la recherche (#102), combien de fois il a été retiré des bookmarks, combien de messages ont été envoyés dans le chat d'un stream, et combien de play, pause et stop le player d'un stream a reçus. Le service n'est jamais exposé au front : tout passe par `main`.

```
search ────MQTT search/hit──────────┐
bookmarks ─MQTT bookmarks/deleted───┤
live-chat ─MQTT chat/message────────┤
main ──────MQTT player/event────────┴──> stats (consumer) ──upsert──> Postgres, schéma stats
                                                                            │
front ──> main ──HTTP GET /stats/...──> stats (API) <───────────────────────┘
```

## Lancer

Depuis la racine du repo, avec l'infra du docker-compose :

    make infra-up
    make stats

ou depuis `stats/` :

    uv run fastapi dev --port 8006

En image Docker, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f stats/Dockerfile -t stats .

Au démarrage, le service crée son schéma et ses tables s'ils n'existent pas, puis se connecte au broker. Il démarre aussi sans Postgres (un warning est journalisé) et sans broker (le client MQTT réessaie toutes les 5 secondes). Si Postgres était absent au démarrage, les tables ne sont créées qu'au redémarrage suivant.

## Configuration

Les variables se mettent dans `stats/.env` (copier `.env.example`).

| Variable       | Défaut                                                                 | Rôle                                   |
|----------------|------------------------------------------------------------------------|----------------------------------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/microservices`  | Base Postgres (driver async psycopg 3) |
| `REDIS_URL`    | `redis://localhost:6379/0`                                             | Cache des lectures (pas encore utilisé) |
| `MQTT_HOST`    | `localhost`                                                            | Hôte du broker MQTT                    |
| `MQTT_PORT`    | `1883`                                                                 | Port du broker MQTT                    |

## Organisation du code

| Fichier           | Rôle |
|-------------------|------|
| `main.py`         | `lifespan` : création du schéma et des tables, abonnements MQTT, démarrage du client |
| `handlers.py`     | Un handler par topic MQTT, qui incrémente le bon compteur |
| `counters.py`     | `increment_counter` : l'upsert commun à tous les compteurs |
| `routers/`        | Routes de lecture des compteurs |
| `models.py`       | Table `counter` |
| `schemas.py`      | Réponses de l'API, une par compteur (`SearchCountResponse`, `BookmarkDeletedCountResponse`, `ChatMessageCountResponse`, `PlayerEventCountResponse`) |
| `database.py`     | Engine async, sessions, dépendance `SessionDep` |
| `utils.py`        | Découpage des clés `type:id` |

## Compteurs

Tous les compteurs sont dans une seule table, `stats.counter` :

| Colonne        | Exemple             | Rôle                                   |
|----------------|---------------------|----------------------------------------|
| `counter_type` | `search/hit`        | Le topic MQTT qui alimente le compteur |
| `key`          | `streamer:42`       | L'élément compté, au format `type:id`  |
| `value`        | `7`                 | Le nombre d'occurrences (`BIGINT`)     |

Le couple (`counter_type`, `key`) est unique. Chaque event fait un upsert (`INSERT ... ON CONFLICT DO UPDATE SET value = value + 1`) : la ligne est créée à 1 au premier event, puis incrémentée par Postgres. Il n'y a pas de lecture préalable, donc deux events simultanés ne perdent pas d'incrément.

La table est générique : un nouveau compteur, c'est un nouveau `counter_type`, sans nouvelle table. La clé est un détail de stockage : l'API la redécoupe et renvoie le type et l'id séparés, avec les noms du domaine (`item_type` / `item_id` pour la recherche, `target_type` / `target_id` pour les bookmarks).

### Events consommés

| Topic               | Modèle            | Clé                       | État |
|---------------------|-------------------|---------------------------|------|
| `search/hit`        | `SearchHit`       | `{item_type}:{item_id}`   | Fait (#102) |
| `bookmarks/deleted` | `BookmarkDeleted` | `{target_type}:{target_id}` | Fait |
| `chat/message`      | `ChatMessage`     | `{stream_id}`             | Fait |
| `player/event`      | `PlayerEvent`     | `{stream_id}:{event_type}` | Fait |

Le client MQTT se connecte avec `client_id="stats"` : la session est persistante, le broker garde les events publiés pendant un arrêt de `stats` et les livre au redémarrage. Les doublons possibles en QoS 1 sont écartés par `MqttClient` grâce à l'`event_id`. Un handler qui échoue n'est pas marqué comme traité, l'event peut être retraité s'il est renvoyé.

## Endpoints

| Chemin                                  | Méthode | Rôle |
|-----------------------------------------|---------|------|
| `/health`                               | GET     | Renvoie `{"status": "ok"}` |
| `/stats/search/{item_type}/{item_id}`   | GET     | Nombre de fois où un élément a été trouvé par la recherche |
| `/stats/search/top`                     | GET     | Éléments les plus trouvés par la recherche |
| `/stats/bookmarks/deleted/{target_type}/{target_id}` | GET | Nombre de fois où une cible a été retirée des bookmarks |
| `/stats/bookmarks/deleted/top`          | GET     | Cibles les plus retirées des bookmarks |
| `/stats/chat/{stream_id}`               | GET     | Nombre de messages envoyés dans le chat d'un stream |
| `/stats/chat/top`                       | GET     | Streams avec le plus de messages dans le chat |
| `/stats/player/{stream_id}`             | GET     | Nombre de play, pause et stop du player d'un stream |

Les routes ne vérifient pas l'identité : `stats` n'est joignable que par `main`, qui réserve les stats de recherche aux admins (`require_admin`). Les routes `/stats/bookmarks/deleted/...`, `/stats/chat/...` et `/stats/player/...` ne sont pas encore relayées par `main`.

### `GET /stats/search/{item_type}/{item_id}`

`item_type` vaut `streamer` ou `message` (sinon `422`). `item_id` est une chaîne : l'id d'un streamer ou l'UUID d'un message. Un élément jamais trouvé renvoie `count: 0`, pas un `404`.

    curl http://localhost:8006/stats/search/streamer/42

```json
{"item_type": "streamer", "item_id": "42", "count": 7}
```

### `GET /stats/search/top`

| Param       | Défaut | Rôle |
|-------------|--------|------|
| `item_type` | aucun  | `streamer` ou `message` pour ne garder qu'un type, tous les types sinon |
| `limit`     | `10`   | Nombre d'éléments, entre 1 et 500 (sinon `422`) |

Le classement est trié par compteur décroissant, puis par clé en cas d'égalité : l'ordre est le même d'un appel à l'autre. La clé est du texte, les égalités suivent donc l'ordre alphabétique et non numérique (`streamer:10` avant `streamer:9`).

    curl "http://localhost:8006/stats/search/top?item_type=streamer&limit=3"

```json
[
  {"item_type": "streamer", "item_id": "3", "count": 78},
  {"item_type": "streamer", "item_id": "42", "count": 51},
  {"item_type": "streamer", "item_id": "7", "count": 12}
]
```

`stats` ne connaît que des ids : les noms des streamers sont à demander au service concerné.

### `GET /stats/bookmarks/deleted/{target_type}/{target_id}`

`target_type` vaut `streamer` ou `replay`, `target_id` est un entier de 1 à 2³¹ − 1 (sinon `422`). Une cible jamais retirée des bookmarks renvoie `count: 0`, pas un `404`.

    curl http://localhost:8006/stats/bookmarks/deleted/streamer/42

```json
{"target_type": "streamer", "target_id": 42, "count": 3}
```

### `GET /stats/bookmarks/deleted/top`

| Param         | Défaut | Rôle |
|---------------|--------|------|
| `target_type` | aucun  | `streamer` ou `replay` pour ne garder qu'un type, tous les types sinon |
| `limit`       | `10`   | Nombre d'éléments, entre 1 et 500 (sinon `422`) |

Même tri que le top de la recherche : compteur décroissant, puis clé texte en cas d'égalité. Comme `target_id` est renvoyé en nombre, attention : à égalité, `replay:10` passe avant `replay:9`.

    curl "http://localhost:8006/stats/bookmarks/deleted/top?target_type=replay&limit=2"

```json
[
  {"target_type": "replay", "target_id": 7, "count": 5},
  {"target_type": "replay", "target_id": 12, "count": 2}
]
```

`bookmarks` peut perdre un event si le broker reste coupé longtemps (voir le README de `bookmarks`) : ce compteur peut donc être légèrement sous-estimé.

### `GET /stats/chat/{stream_id}`

`stream_id` est un entier de 1 à 2³¹ − 1 (sinon `422`). Un stream sans message renvoie `count: 0`, pas un `404`. `stats` ne vérifie pas que le stream existe.

    curl http://localhost:8006/stats/chat/12

```json
{"stream_id": 12, "count": 1530}
```

### `GET /stats/chat/top`

| Param   | Défaut | Rôle |
|---------|--------|------|
| `limit` | `10`   | Nombre de streams, entre 1 et 500 (sinon `422`) |

Pas de filtre : un message n'a pas de type. Même tri que les autres tops : compteur décroissant, puis clé texte en cas d'égalité (`10` passe avant `9`).

    curl "http://localhost:8006/stats/chat/top?limit=2"

```json
[
  {"stream_id": 12, "count": 1530},
  {"stream_id": 3, "count": 412}
]
```

`/stats/chat/top` est déclarée avant `/stats/chat/{stream_id}` : les deux chemins ont le même nombre de segments, et FastAPI essaie les routes dans l'ordre. Dans l'autre sens, `top` serait lu comme un `stream_id` et la route répondrait toujours `422`.

### `GET /stats/player/{stream_id}`

`stream_id` est un entier de 1 à 2³¹ − 1 (sinon `422`). La route renvoie les trois compteurs du stream en une réponse, avec `0` pour un type d'event jamais reçu. Pas de classement : le ticket ne demande que le détail par stream.

    curl http://localhost:8006/stats/player/12

```json
{"stream_id": 12, "play": 88, "pause": 31, "stop": 0}
```

Un stream a jusqu'à trois lignes en base (`12:play`, `12:pause`, `12:stop`). La route les lit en une requête, avec les trois clés exactes (`key IN (...)`) : le stream `1` ne récupère donc jamais les lignes du stream `12`.

Les types d'events (`play`, `pause`, `stop`) sont écrits à trois endroits qui doivent rester alignés : le `Literal` de `PlayerEvent.event_type` dans `common`, la liste `EVENT_TYPES` de `routers/player.py`, et les champs de `PlayerEventCountResponse`. Un nouveau type ajouté dans `common` serait compté en base, mais n'apparaîtrait pas dans la réponse tant que les deux autres ne sont pas mis à jour.

## Tests

    uv run pytest

Les tests n'ont besoin ni de Postgres ni de Mosquitto : ils tournent sur SQLite en mémoire (`aiosqlite`), sans schéma (`schema_translate_map`). L'upsert Postgres passe aussi sur SQLite. Les routes sont testées avec un `AsyncClient` dont la session est remplacée, les handlers avec `monkeypatch` sur `SessionLocal`. Un fichier de tests par compteur : `test_search.py`, `test_bookmarks.py`, `test_chat.py` et `test_player.py`.
