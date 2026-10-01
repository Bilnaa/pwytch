# search

Recherche de streamers (US-SE1, #23). `search` construit son propre index à partir des events MQTT `stream/started` et `stream/ended`, puis expose `GET /search/streamers`. La recherche ignore la casse et les accents, et trouve une sous-chaîne n'importe où dans le nom du streamer, le titre ou le jeu de son dernier live.

```
stream ──MQTT stream/started, stream/ended──> search (consumer) ──> Postgres, schéma search
                                                                          │
front ──> main ──HTTP GET /search/streamers?q=──> search (API) <──────────┘
```

## Lancer

Depuis la racine du repo, avec l'infra du docker-compose :

    docker compose up -d postgres mqtt
    make search

ou depuis `search/` :

    uv run fastapi dev --port 8004

En image Docker, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f search/Dockerfile -t search .

Au démarrage, le service crée son schéma, ses tables et l'extension `pg_trgm` s'ils n'existent pas, puis se connecte au broker. Aucune action manuelle sur la base.

## Configuration

Les variables se mettent dans `search/.env` (copier `.env.example`).

| Variable       | Défaut                                                                | Rôle                  |
|----------------|-----------------------------------------------------------------------|-----------------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/microservices` | Base Postgres         |
| `MQTT_HOST`    | `localhost`                                                           | Hôte du broker MQTT   |
| `MQTT_PORT`    | `1883`                                                                | Port du broker MQTT   |

### Base de données : une base partagée, un schéma par service

Le docker-compose crée une seule base, `microservices`, pour toute l'équipe. `search` range ses tables dans son propre schéma Postgres, `search` (`search.streamers`, `search.streams`). Deux services peuvent ainsi avoir une table du même nom (`streams` côté `stream` par exemple) sans collision.

Convention proposée à l'équipe : chaque service crée et utilise un schéma à son nom. Ce choix remplace la « base par service » envisagée dans #4.

Les tests n'ont besoin ni de Postgres ni de Mosquitto : ils tournent sur SQLite en mémoire, sans schéma.

## Endpoints

| Chemin               | Méthode | Rôle                        |
|----------------------|---------|-----------------------------|
| `/health`            | GET     | Renvoie `{"status": "ok"}`  |
| `/search/streamers`  | GET     | Recherche de streamers      |

### `GET /search/streamers`

| Paramètre | Règle                                                   | Défaut |
|-----------|---------------------------------------------------------|--------|
| `q`       | obligatoire, entre 2 et 100 caractères après `strip`    | —      |
| `page`    | entier ≥ 1                                              | `1`    |
| `size`    | entier entre 1 et 50                                    | `20`   |

Tri : streamers en live d'abord, puis nom sans tenir compte de la casse, puis `streamer_id`. `%` et `_` dans `q` sont cherchés littéralement.

200, `GET /search/streamers?q=cel` :

```json
{
  "items": [
    {
      "streamer_id": 42,
      "streamer_name": "Célèste",
      "last_title": "Speedrun any%",
      "last_game": "Celeste",
      "is_live": true,
      "live_stream_id": 7
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20
}
```

- `live_stream_id` vaut `null` quand `is_live` est `false`.
- `last_title` et `last_game` viennent du dernier live du streamer, et peuvent être `null`.

200 sans résultat : `{"items": [], "total": 0, "page": 1, "size": 20}`. Une page au-delà de la fin renvoie aussi `items: []`, avec le vrai `total`.

422 quand un paramètre est invalide (`q` absent, trop court ou trop long, `page` ou `size` hors bornes), au format par défaut de FastAPI :

```json
{"detail": [{"type": "string_too_short", "loc": ["query", "q"], "msg": "String should have at least 2 characters", "...": "..."}]}
```

## Topics consommés

Souscrits en QoS 1. Les modèles viennent de `common.events`.

| Topic            | Event           | Effet sur l'index                                                       |
|------------------|-----------------|-------------------------------------------------------------------------|
| `stream/started` | `StreamStarted` | Crée ou met à jour le live et le streamer, recalcule le texte cherché   |
| `stream/ended`   | `StreamEnded`   | Marque le live comme terminé                                            |

Les handlers acceptent les doublons et le désordre (un `ended` reçu avant son `started`). Un message invalide est logué en `WARNING` puis ignoré. Si le broker est injoignable, le consumer réessaie après 1 s, 2 s, 4 s… jusqu'à 30 s, et l'API continue de répondre.

## Test

    uv run pytest

## Vérification manuelle de `pg_trgm`

L'index GIN trigramme accélère `LIKE '%…%'`. Les tests sur SQLite ne peuvent pas le vérifier. Avec quelques streamers indexés :

    docker compose exec postgres psql -U postgres microservices

```sql
SET enable_seqscan = off;
EXPLAIN SELECT * FROM search.streamers WHERE search_text LIKE '%cel%';
```

Le plan doit contenir `Bitmap Index Scan on ix_streamers_search_text_trgm`. Une requête de 2 caractères n'utilise pas l'index (un trigramme fait 3 caractères) : c'est attendu.

## Dettes connues

- **Pas de migration** : `create_all` crée les tables absentes mais ne modifie pas les tables existantes. Après un changement de colonne (ids passés de texte à entier par exemple), supprimer le schéma en local : `DROP SCHEMA search CASCADE;`. Alembic sera nécessaire au premier changement de schéma sur une base qui a des données à garder.

- **Event perdu si le handler échoue** (base indisponible par exemple) : le message est logué en `ERROR` puis abandonné. À traiter avec #11.
- **Messages perdus pendant une coupure du broker** : le client MQTT démarre avec une session propre. Pour les récupérer, il faudra un `identifier` fixe et `clean_session=False`.
- **Format des erreurs 422** : format par défaut de FastAPI. À remplacer par `common.errors` quand #2 sera mergée.
- **Pas de migrations** : le schéma est créé par `create_all` au démarrage, sans Alembic. Une colonne ajoutée plus tard ne sera pas créée sur une base existante.
- **Consumer MQTT local** : à remplacer par le client partagé `common.mqtt` quand il existera.
- **Tri des noms accentués** : `lower()` de SQLite ne traite que l'ASCII, donc l'ordre des noms accentués peut différer entre les tests et Postgres.
