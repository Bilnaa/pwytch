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
| `/replays/{stream_id}/download` | GET | Téléchargement en `.mp4`, converti à la première demande |

Un replay est un live terminé (`ended_at` et `duration_s` renseignés) : un live en cours n'apparaît dans aucune route. Son identifiant est le `stream_id` du live.

### `GET /replays`

Renvoie une `Page[ReplayResult]` (`common.pagination`), du replay le plus récemment terminé au plus ancien (`ended_at` décroissant, puis `stream_id` décroissant).

| Paramètre     | Règle                                                  |
|---------------|--------------------------------------------------------|
| `page`        | entier entre 1 et 2 147 483 647, défaut 1              |
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

- `playback_url` est relatif à la racine de l'API de `main` (`/api`), qui relaie la playlist de `stream`. URL complète : `{origine de main}/api/lives/42/index.m3u8` ; côté front, `apiUrl(playback_url)`. Sans le `/api`, `main` renvoie la page du front et le lecteur reçoit un 404.
- `streamer_name`, `title`, `game` et `started_at` peuvent valoir `null` (voir « Dettes connues »).
- `mp4_status` : `none`, `processing`, `ready` ou `failed`, l'état de la conversion en `.mp4`.

422 : `page`, `size` ou `streamer_id` hors bornes.

### `GET /replays/{stream_id}`

Renvoie un `ReplayResult`, même format qu'un élément de la liste.

- 404 `{"detail": "Replay not found"}` : replay inconnu ou live encore en cours.
- 422 : `stream_id` non numérique, ≤ 0 ou au-delà de 2 147 483 647. Comme partout avec FastAPI, une chaîne numérique est convertie : `42.0` ou `+42` donnent le replay 42.

### `GET /replays/{stream_id}/download`

Le `.mp4` n'est produit qu'à la demande : le premier appel lance la conversion et répond 202, le client redemande après `Retry-After`.

| État du replay                       | Réponse                                                                                       |
|--------------------------------------|-----------------------------------------------------------------------------------------------|
| Inconnu ou live en cours             | 404 `{"detail": "Replay not found"}`                                                          |
| `ready`, fichier présent             | 200, le fichier en `video/mp4`, `Content-Disposition: attachment; filename="replay-{id}.mp4"` |
| `ready`, fichier disparu             | statut remis à `none`, puis comme `none`                                                      |
| `none`                               | conversion lancée, 202 `{"stream_id": id, "mp4_status": "processing"}`, `Retry-After: 5`     |
| `processing`                         | 202, même corps et même en-tête, aucun second ffmpeg                                          |
| `failed`                             | 500 `{"detail": "Conversion failed, try again"}`, statut remis à `none` : l'appel suivant relance la conversion |

422 : `stream_id` non numérique, ≤ 0 ou au-delà de 2 147 483 647.

La conversion tourne en tâche de fond, après l'envoi du 202, avec ses propres sessions : la session de la requête est déjà rendue. `main` relaie le 202 tel quel (#99).

Vérification manuelle, avec un replay terminé dont la playlist est servie par `stream` :

```bash
curl -i localhost:8003/replays/1/download      # 202, Retry-After: 5
sleep 5
curl -OJ localhost:8003/replays/1/download     # replay-1.mp4
```

## Conversion `.mp4`

`replay` lit la playlist HLS d'un live terminé directement chez `stream`, sans dossier partagé, et la recopie dans un `.mp4` sans réencoder :

    ffmpeg -nostdin -y -loglevel error -i {STREAM_URL}/lives/{stream_id}/index.m3u8 -c copy -f mp4 {REPLAYS_DIR}/{stream_id}.mp4.part

| `mp4_status` | Sens                                                                |
|--------------|---------------------------------------------------------------------|
| `none`       | Pas de `.mp4`, aucune conversion en cours                           |
| `processing` | ffmpeg tourne                                                       |
| `ready`      | `REPLAYS_DIR/{stream_id}.mp4` est prêt                              |
| `failed`     | ffmpeg a échoué ; la fin de son stderr est dans les logs en `ERROR` |

- **Une seule conversion par replay** : `none` passe à `processing` par une seule requête `UPDATE ... WHERE mp4_status = 'none'`. Deux demandes simultanées ne lancent qu'un ffmpeg, même avec plusieurs workers.
- **Jamais de fichier incomplet servi** : ffmpeg écrit dans `{stream_id}.mp4.part`, renommé en `.mp4` seulement si ffmpeg finit avec le code 0. En cas d'échec, le `.part` est supprimé.
- **Délai maximal** : au-delà de `CONVERSION_TIMEOUT_S` (600 s), ffmpeg est tué et le replay passe à `failed`. ffmpeg absent de la machine donne aussi `failed`.
- **Au démarrage** : les `*.mp4.part` restants sont supprimés et les lignes en `processing` repassent à `none` (un arrêt du service a tué leur ffmpeg). `REPLAYS_DIR` est créé s'il manque. Base coupée : un `WARNING`, et le service démarre quand même.
- L'image Docker installe ffmpeg. En local, il faut `ffmpeg` dans le `PATH`.

Vérifié avec un vrai ffmpeg sur une playlist servie par `stream` (H.264 + AAC, 3 segments) : `.mp4` de 12 s, codecs `h264` et `aac`, sans option de flux audio en plus. Sur un live inconnu, ffmpeg écrit `Server returned 404 Not Found` et le replay passe à `failed`.

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
- **Identifiants de live réutilisés en dev** : si la base de `main` est recréée, les `stream_id` repartent de 1 alors que celle de `replay` garde ses lignes. Le nouveau live 1 reprend la ligne de l'ancien replay 1 : il est listé comme terminé pendant qu'il tourne, et son vrai `stream/ended` est ignoré comme doublon. Recréer la base de `replay` en même temps que celle de `main` (`DROP TABLE replays;`).
- **Pagination par décalage** : `page` et `size` se traduisent en `OFFSET`. Si un live se termine entre deux appels, la liste se décale d'un cran et un replay apparaît sur deux pages ; `total` et `items` sont lus par deux requêtes séparées. Le client dédoublonne par `stream_id` ; une pagination par curseur sera nécessaire pour un défilement infini.
- **Les `.mp4` ne sont jamais supprimés** : ils restent dans `REPLAYS_DIR` (volume `replays-data` en conteneur) tant que personne ne les efface.
- **Conversion interrompue non reprise** : un arrêt du service pendant ffmpeg remet la ligne à `none` au démarrage, et la conversion repart seulement à la prochaine demande.
- **Statut bloqué en `processing`** si la base tombe pendant une conversion : le statut final n'est pas écrit (erreur journalisée), et le prochain démarrage le remet à `none`.
- **Pas de migration** : `create_all` crée les tables absentes mais ne modifie pas une table existante. Après un changement de colonne, supprimer la table en local : `DROP TABLE replays;`. Alembic sera nécessaire au premier changement de schéma sur une base qui a des données à garder.
