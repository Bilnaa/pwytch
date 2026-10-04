# replay

Replays des lives terminés (#94, #115, #95, #97, #98). `replay` apprend le début et la fin de chaque live par MQTT (`stream/started`, `stream/ended`), garde un replay par live dans sa base, et convertit un replay en `.mp4` à la demande en lisant la playlist HLS directement chez `stream`.

```
stream ──MQTT stream/started, stream/ended──> replay (consumer) ──> Postgres, base replay
stream <──HTTP HEAD playlist (reason error)── replay
stream <──HTTP GET playlist + segments (ffmpeg)── replay ──> REPLAYS_DIR/{stream_id}.mp4
front ──> main ──HTTP GET /replays...──> replay (API)
```

## Lancer

Depuis la racine du repo, avec l'infra du docker-compose :

    make infra-up
    make replay

ou depuis `replay/` :

    uv run fastapi dev --port 8003

En image Docker, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f replay/Dockerfile -t replay .

Au démarrage, le service crée ses tables si elles n'existent pas. La base `replay` est créée par `infra/postgres/init.sql`, qui ne s'exécute que sur un volume Postgres vide : sur un volume plus ancien, la créer à la main avec `docker compose exec postgres createdb -U postgres replay`.

## Configuration

Les variables se mettent dans `replay/.env` (copier `.env.example`, ou `make dev` depuis la racine).

| Variable               | Défaut                                                          | Rôle                                       |
|------------------------|-----------------------------------------------------------------|--------------------------------------------|
| `DATABASE_URL`         | `postgresql+asyncpg://postgres:postgres@localhost:5432/replay`  | Base Postgres du service                   |
| `MQTT_HOST`            | `localhost`                                                     | Hôte du broker MQTT                        |
| `MQTT_PORT`            | `1883`                                                          | Port du broker MQTT                        |
| `STREAM_URL`           | `http://localhost:8001`                                         | `stream`, qui sert les playlists et segments |
| `REPLAYS_DIR`          | `replays`                                                       | Dossier des `.mp4`, ignoré par Git         |
| `STREAM_TIMEOUT_S`     | `5`                                                             | Délai des appels HTTP vers `stream`        |
| `CONVERSION_TIMEOUT_S` | `600`                                                           | Durée maximale d'une conversion ffmpeg     |

## Modèle

Une table, `replays`, une ligne par live. `stream_id` est la clé et l'identifiant public du replay.

| Colonne                              | Note                                                    |
|--------------------------------------|---------------------------------------------------------|
| `stream_id`                          | Clé primaire, identifiant du live                       |
| `streamer_id`                        | Indexé, pour filtrer par streamer                       |
| `streamer_name`, `title`, `game`, `started_at` | Nuls tant que `stream/started` n'est pas arrivé |
| `ended_at`, `duration_s`             | Nuls tant que le live tourne : la ligne est alors invisible |
| `mp4_status`                         | `none`, `processing`, `ready` ou `failed`, défaut `none` |

## Tests

    uv run pytest

Les tests n'ont besoin ni de Postgres ni de Mosquitto : ils tournent sur SQLite en mémoire.

## Dettes connues

- **Pas de migration** : `create_all` crée les tables absentes mais ne modifie pas une table existante. Après un changement de colonne, supprimer la table en local : `DROP TABLE replays;`. Alembic sera nécessaire au premier changement de schéma sur une base qui a des données à garder.
