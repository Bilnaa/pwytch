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

ou en conteneur, avec le docker-compose (profil `apps`, pas lancé par `make infra-up`) :

    docker compose --profile apps up -d --build replay

Le conteneur écoute sur le port 8003, parle à `postgres`, `mqtt` et `stream` par leurs noms de service, et garde les `.mp4` dans le volume `replays-data`. Arrêter `make replay` avant : une seule instance à la fois (voir « Dettes connues »).

En image Docker seule, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f replay/Dockerfile -t replay .

Au démarrage, le service crée ses tables si elles n'existent pas. Si Postgres est injoignable, il démarre quand même et journalise un `WARNING` (même comportement que `stats`) ; les tables seront créées au prochain redémarrage. La base `replay` est créée par `infra/postgres/init.sql`, qui ne s'exécute que sur un volume Postgres vide : sur un volume plus ancien, la créer à la main avec `docker compose exec postgres createdb -U postgres replay`.

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

## Endpoints

| Chemin                  | Méthode | Rôle                                   |
|-------------------------|---------|----------------------------------------|
| `/health`               | GET     | Renvoie `{"status": "ok"}`             |
| `/replays`              | GET     | Liste des replays, paginée             |
| `/replays/{stream_id}`  | GET     | Détail d'un replay                     |

Un replay est un live terminé : un live en cours n'apparaît dans aucune route. Son identifiant est le `stream_id` du live.

### `GET /replays`

Renvoie une `Page[ReplayResult]` (`common.pagination`), du replay le plus récemment terminé au plus ancien (`ended_at` décroissant, puis `stream_id` décroissant).

| Paramètre     | Règle                                                  |
|---------------|--------------------------------------------------------|
| `page`        | entier ≥ 1, défaut 1                                   |
| `size`        | entier entre 1 et 50, défaut 20                        |
| `streamer_id` | optionnel, entier entre 1 et 2 147 483 647             |

`total` compte tous les replays qui passent le filtre. Une page au-delà de la fin renvoie `items: []`.

200, `GET /replays?size=1` :

```json
{
  "items": [
    {
      "stream_id": 42,
      "streamer_id": 7,
      "streamer_name": "Célèste",
      "title": "Speedrun Any%",
      "game": "Celeste",
      "started_at": "2026-10-04T20:00:00Z",
      "ended_at": "2026-10-04T21:30:00Z",
      "duration_s": 5400.0,
      "mp4_status": "none",
      "playback_url": "/lives/42/index.m3u8"
    }
  ],
  "total": 3,
  "page": 1,
  "size": 1
}
```

- `playback_url` est relatif à `main`, qui relaie la playlist de `stream` ; le front ajoute l'origine.
- `streamer_name`, `title`, `game` et `started_at` peuvent valoir `null` (voir « Dettes connues »).
- `mp4_status` : `none`, `processing`, `ready` ou `failed`, l'état de la conversion en `.mp4`.

422 : `page`, `size` ou `streamer_id` hors bornes.

### `GET /replays/{stream_id}`

Renvoie un `ReplayResult`, même format qu'un élément de la liste.

- 404 `{"detail": "Replay not found"}` : replay inconnu ou live encore en cours.
- 422 : `stream_id` non entier, nul ou au-delà de 2 147 483 647.

## Topics consommés

Souscrits en QoS 1 avec le `client_id` fixe `replay` : la session est persistante, le broker garde les messages publiés pendant que `replay` est arrêté. Un message en cours de traitement au moment de l'arrêt est perdu (voir « Dettes connues »). Les modèles viennent de `common.events`.

| Topic            | Event           | Effet                                                                                   |
|------------------|-----------------|-----------------------------------------------------------------------------------------|
| `stream/started` | `StreamStarted` | Crée ou complète la ligne du live (streamer, titre, jeu, début). Elle reste invisible.  |
| `stream/ended`   | `StreamEnded`   | Renseigne `ended_at` et `duration_s` : le replay devient visible.                       |

Les deux events peuvent arriver dans n'importe quel ordre : chaque handler crée la ligne si elle manque et ne touche pas aux champs de l'autre. Un `stream/ended` reçu une seconde fois est ignoré.

Avec `reason: "error"`, `replay` envoie d'abord `HEAD {STREAM_URL}/lives/{stream_id}/index.m3u8` :

| Réponse de `stream`                 | Effet                                                        |
|-------------------------------------|--------------------------------------------------------------|
| 2xx                                 | Le replay est créé                                           |
| 404                                 | Aucun replay : ffmpeg n'a rien produit, la ligne est supprimée |
| Injoignable, timeout, autre statut  | Le replay est créé quand même, avec un `WARNING`             |

### Vérification manuelle

Depuis la racine, avec `make infra-up` puis `make replay` :

```bash
docker compose exec mqtt mosquitto_pub -q 1 -t stream/started -m '{"stream_id": 1, "streamer_id": 1, "streamer_name": "Zerator", "title": "Speedrun", "game": "Celeste", "started_at": "2026-10-04T14:00:00Z"}'
docker compose exec mqtt mosquitto_pub -q 1 -t stream/ended -m '{"stream_id": 1, "streamer_id": 1, "ended_at": "2026-10-04T15:00:00Z", "duration_s": 3600, "reason": "normal"}'
docker compose exec postgres psql -U postgres replay -c 'SELECT stream_id, title, ended_at FROM replays'
```

Attendu : une ligne `1 | Speedrun | 2026-10-04 15:00:00+00`. Avec `"reason": "error"` et `stream` arrêté, la ligne est créée et les logs de `replay` montrent `Playlist of live … not checked, replay kept`.

## Tests

    uv run pytest

Les tests n'ont besoin ni de Postgres ni de Mosquitto : ils tournent sur SQLite en mémoire.

## Dettes connues

- **Tables absentes si la base était coupée au démarrage** : le service tourne, mais les requêtes échouent tant qu'il n'a pas été redémarré avec la base disponible.
- **Event perdu si un handler échoue** (base indisponible par exemple) : `MqttClient` le journalise en `ERROR` puis l'abandonne. À traiter avec #11.
- **Events en attente pendant le `HEAD` vers `stream`** : `MqttClient` traite les messages un par un et le `HEAD` est fait dans le handler de `stream/ended`. Si `stream` ne répond pas, tous les events suivants attendent jusqu'à `STREAM_TIMEOUT_S` (5 s). Acceptable avec notre volume ; sinon, sortir la vérification du handler.
- **Replay visible sans titre** : si `stream/ended` arrive avant `stream/started`, le replay est visible tout de suite avec `streamer_name`, `title`, `game` et `started_at` à `null`, et le reste si `stream/started` est perdu. Choix assumé : on préfère montrer le replay que le cacher ; les routes de #95 renvoient donc ces champs en nullable.
- **Event perdu à l'arrêt** : `mqtt.stop()` annule le handler en cours, par exemple un `stream/ended` qui attend le `HEAD` vers `stream` (jusqu'à `STREAM_TIMEOUT_S`). Le message QoS 1 est acquitté dès sa réception, le broker ne le renvoie pas : le live reste invisible. Même cause que la ligne précédente (acquittement avant traitement, dans `common.mqtt`), à traiter avec #11.
- **Deux instances avec le même `client_id`** : le broker déconnecte la première quand la seconde se connecte, et elles se volent la session en boucle ; des events partent vers la mauvaise instance ou se perdent. Une seule instance de `replay` à la fois : ne pas lancer `make replay` pendant que le conteneur tourne.
- **Ligne invisible pour toujours** : un `stream/ended` en erreur, sans playlist, reçu avant son `stream/started` ne supprime rien ; la ligne créée ensuite par `stream/started` n'a jamais de `ended_at`. Sans effet pour l'utilisateur.
- **Pas de migration** : `create_all` crée les tables absentes mais ne modifie pas une table existante. Après un changement de colonne, supprimer la table en local : `DROP TABLE replays;`. Alembic sera nécessaire au premier changement de schéma sur une base qui a des données à garder.
