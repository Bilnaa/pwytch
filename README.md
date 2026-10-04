# Pwytch

Plateforme de live streaming découpée en microservices FastAPI. Un dossier par service, chaque service a sa base, son `pyproject.toml` et son README. Le backlog est sur le [board Pwytch v2](https://github.com/orgs/coding-factory-learnd/projects/9).

## Services

| Service     | Rôle                                                                 | Port | Responsable  |
|-------------|----------------------------------------------------------------------|------|--------------|
| `main`      | Point d'entrée unique du front : comptes, JWT, relais vers les autres | 8000 | celianloisel |
| `stream`    | Reçoit le flux WebM du streamer et le convertit en HLS avec ffmpeg    | 8001 | Bilnaa       |
| `live-chat` | Salon de chat WebSocket par live                                     | 8002 | Geuzivv      |
| `replay`    | Replays des lives terminés, conversion et téléchargement en `.mp4`   | 8003 | ArKZbeb      |
| `search`    | Recherche de streamers et dans le chat d'un live                     | 8004 | ArKZbeb      |
| `bookmarks` | Bookmarks des utilisateurs                                           | 8005 | Railas9      |
| `stats`     | Compteurs (recherche, chat, player, bookmarks)                       | 8006 | Railas9      |
| `web`       | Front React, servi par `main` une fois buildé (`make web` en dev)      | 5173 | -            |
| `common`    | Bibliothèque partagée : modèles des events MQTT, topics, client MQTT | -    | -            |

Le front ne parle qu'à `main`. Aucun service n'importe le code d'un autre, seul `common` est partagé, et aucun service ne lit la base d'un autre.

## Lancer le projet

Prérequis : [uv](https://docs.astral.sh/uv/), Docker, et ffmpeg pour `stream`.

```bash
make dev        # copie les .env.example en .env et installe chaque service
make infra-up   # PostgreSQL, Redis et Mosquitto
```

Puis un terminal par service :

```bash
make main
make stream
make search
# ...
make web       # front en dev sur http://localhost:5173
```

Pour le front servi par `main` sur http://localhost:8000 : `make web-build`, puis redémarrer `main`. Il faut [Node.js](https://nodejs.org/) 22 ou plus.

Autres commandes (`make help` pour la liste complète) :

```bash
make test       # tests de tous les services
make lint       # ruff sur tous les services
make infra-down
make init name=<service>   # nouveau service depuis le template cookiecutter
```

Le compose crée une base par service au premier démarrage (`infra/postgres/init.sql`). Si le volume postgres existe déjà, il faut le recréer une fois avec `docker compose down -v`.

## Topics MQTT

Les modèles des events sont dans `common/src/common/events.py`, les noms des topics dans `common/src/common/topics.py`. Le service qui produit un event ajoute son modèle dans `common`.

| Topic               | Producteur  | Consommateurs                 | Modèle dans `common` |
|---------------------|-------------|-------------------------------|----------------------|
| `stream/started`    | `stream`    | `main`, `search`, `replay`    | `StreamStarted`      |
| `stream/ended`      | `stream`    | `main`, `search`, `replay`    | `StreamEnded`        |
| `chat/message`      | `live-chat` | `search`, `stats`             | `ChatMessage`        |
| `search/hit`        | `search`    | `stats`                       | `SearchHit`          |
| `player/event`      | `main`      | `stats`                       | `PlayerEvent`        |
| `bookmarks/deleted` | `bookmarks` | `stats`                       | `BookmarkDeleted` (à venir, #117) |

## HTTP, WebSocket ou MQTT

Par défaut, un service prévient les autres avec un event MQTT : le producteur n'attend personne et ne sait pas qui écoute. On reste en direct dans ces cas :

- **HTTP de `main` vers un service** (lives, recherche, replays, bookmarks, stats) : le front attend une réponse tout de suite, c'est une question et pas un fait à annoncer. `main` relaie la requête et renvoie la réponse du service.
- **WebSocket `main` → `stream` pour l'ingest** : le flux vidéo est continu et binaire, il ne passe pas par le broker. `main` vérifie le jeton puis recopie chaque morceau.
- **WebSocket `main` → `live-chat` pour le chat** : les messages vont dans les deux sens en temps réel avec un viewer connecté. `main` vérifie le jeton puis relaie.
- **HTTP pour `/health`** : `main` interroge les autres services pour savoir s'ils répondent.

## Branches et PR

- `main` : ce qui est rendu. Seules `develop` et les branches `hotfix/*` peuvent y être mergées.
- `develop` : branche de travail, toutes les PR la visent.
- Les branches commencent par `feature/`, `fix/`, `chore/`, `docs/`, `hotfix/` ou `microservice/`. La CI le vérifie, lance ruff et les tests de chaque service, et lint puis build le front.
- Un ticket = un dossier de service. La PR a le label `ms:<service>` du dossier touché.
- Comme les PR visent `develop`, `Closes #N` ne ferme rien : on met un commentaire `Ticket : #N` sur la PR et `PR : #N` sur le ticket, et la carte passe en « In review ».
- Une fois mergée : cases cochées, ticket fermé, carte en « Done ».
