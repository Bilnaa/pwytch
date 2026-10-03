# search

Recherche de streamers (US-SE1, #23) et recherche dans le chat d'un live (US-SE2, #87, #88). `search` construit son propre index à partir des events MQTT `stream/started`, `stream/ended` et `chat/message`, puis expose `GET /search/streamers` et `GET /search/streams/{stream_id}/messages`. La recherche ignore la casse et les accents, et trouve une sous-chaîne n'importe où : nom du streamer, titre ou jeu de son dernier live pour les streamers, contenu du message pour le chat.

```
stream ────MQTT stream/started, stream/ended──> search (consumer) ──> Postgres, schéma search
live-chat ──MQTT chat/message─────────────────────┘                          │
front ──> main ──HTTP GET /search/...?q=──> search (API) <────────────────────┘
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

Le docker-compose crée une seule base, `microservices`, pour toute l'équipe. `search` range ses tables dans son propre schéma Postgres, `search` (`search.streamers`, `search.streams`, `search.chat_messages`). Deux services peuvent ainsi avoir une table du même nom (`streams` côté `stream` par exemple) sans collision.

Convention proposée à l'équipe : chaque service crée et utilise un schéma à son nom. Ce choix remplace la « base par service » envisagée dans #4.

Les tests n'ont besoin ni de Postgres ni de Mosquitto : ils tournent sur SQLite en mémoire, sans schéma.

## Endpoints

| Chemin               | Méthode | Rôle                        |
|----------------------|---------|-----------------------------|
| `/health`            | GET     | Renvoie `{"status": "ok"}`  |
| `/search/streamers`  | GET     | Recherche de streamers      |
| `/search/streams/{stream_id}/messages` | GET | Recherche dans le chat d'un live |

### `GET /search/streamers`

| Paramètre | Règle                                                   | Défaut |
|-----------|---------------------------------------------------------|--------|
| `q`       | obligatoire, entre 2 et 100 caractères après `strip`, non vide après normalisation | —      |
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

422 quand un paramètre est invalide (`q` absent, trop court, trop long ou vide après normalisation, `page` ou `size` hors bornes), au format par défaut de FastAPI :

```json
{"detail": [{"type": "string_too_short", "loc": ["query", "q"], "msg": "String should have at least 2 characters", "...": "..."}]}
```

### `GET /search/streams/{stream_id}/messages`

Renvoie les 10 messages les plus récents du live qui contiennent `q`. Marche aussi pour un live terminé.

| Paramètre   | Règle                                                                              |
|-------------|------------------------------------------------------------------------------------|
| `stream_id` | chemin, entier entre 1 et 2 147 483 647                                            |
| `q`         | obligatoire, entre 1 et 100 caractères après `strip`, non vide après normalisation |

Un seul caractère suffit (`?`, un emoji), alors que `/search/streamers` en demande 2. Pas de `page` ni de `size`. Tri : `sent_at` décroissant, puis `message_id` décroissant. `%` et `_` dans `q` sont cherchés littéralement.

200, `GET /search/streams/7/messages?q=gg` :

```json
[
  {
    "message_id": "3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97",
    "stream_id": 7,
    "author_name": "Célèste",
    "content": "GG WP !",
    "sent_at": "2026-10-02T20:14:03Z"
  }
]
```

200 `[]` : aucune correspondance, ou `stream_id` inconnu de `search`. `content` est renvoyé tel que publié ; l'id de l'auteur est stocké mais jamais renvoyé.

422 : `q` absent, vide, fait d'espaces, de plus de 100 caractères, ou vide après normalisation ; `stream_id` non entier, nul ou au-delà de 2 147 483 647.

Sur les deux routes, « vide après normalisation » vise un `q` fait seulement de diacritiques combinants (U+0301 par exemple) : sans ce contrôle, la requête correspondrait à tout.

## Topics consommés

Souscrits en QoS 1. Les modèles viennent de `common.events`.

| Topic            | Event           | Effet sur l'index                                                       |
|------------------|-----------------|-------------------------------------------------------------------------|
| `stream/started` | `StreamStarted` | Crée ou met à jour le live et le streamer, recalcule le texte cherché   |
| `stream/ended`   | `StreamEnded`   | Marque le live comme terminé                                            |
| `chat/message`   | `ChatMessage`   | Stocke le message et son texte normalisé, si `message_id` est nouveau   |

Le consumer est le `MqttClient` de `common.mqtt`, créé dans `app/mqtt.py` et démarré par le `lifespan` :

- `client_id` fixe, `search` : la session est persistante, le broker garde les messages QoS 1 publiés pendant un redémarrage de `search` ;
- si le broker est injoignable, le client réessaie toutes les 5 s, et l'API continue de répondre ;
- un message invalide est logué en `WARNING` par `common` puis ignoré ;
- chaque event ouvre sa propre session de base ; si le handler lève, la session est fermée sans commit et `common` logue l'erreur en `ERROR` ;
- `common` ignore un `event_id` déjà traité (les 1000 derniers, en mémoire). Les handlers restent idempotents : un doublon avec un nouvel `event_id`, un redémarrage, un `ended` reçu avant son `started`. Un `chat/message` déjà stocké n'est jamais réécrit (le premier gagne) ; s'il diffère sur le live, l'auteur ou le contenu, un `WARNING` est logué avec le `message_id`.

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

## Vérifications manuelles de la recherche dans le chat

Depuis la racine, avec `docker compose up -d postgres mqtt`, puis `make search`.

1. Publier un message :

```bash
docker compose exec mqtt mosquitto_pub -q 1 -t chat/message -m '{"message_id": "3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97", "stream_id": 1, "author_id": 1, "author_name": "alice", "content": "GG WP !", "sent_at": "2026-10-02T20:14:03Z"}'
```

2. `curl 'localhost:8004/search/streams/1/messages?q=gg'` : le message est renvoyé.
3. Session persistante : arrêter `search`, publier un message avec un autre `message_id` (`uuidgen`), relancer `make search`. Le `curl` renvoie les deux messages.
4. `docker compose stop mqtt` : l'API répond toujours. `docker compose start mqtt` : les logs montrent la reconnexion.
5. Plan de requête, dans `docker compose exec postgres psql -U postgres microservices` :

```sql
SET enable_seqscan = off;
SET enable_bitmapscan = off;
EXPLAIN SELECT * FROM search.chat_messages WHERE stream_id = 1 AND search_text LIKE '%gg%'
ORDER BY sent_at DESC, message_id DESC LIMIT 10;
```

Attendu : `Index Scan Backward` sur `ix_chat_messages_stream_id_sent_at_message_id`, sans nœud `Sort` ni `Incremental Sort`. Sans `enable_bitmapscan = off`, Postgres choisit sur une petite table un `Bitmap Index Scan` suivi d'un `Sort` (vérifié avec 2 messages). Ces deux réglages prouvent que l'index peut servir à cette requête, pas que Postgres le choisit : avec peu de lignes, un autre plan est normal. Ce n'est pas une mesure de performance.

## Dettes connues

- **Pas de migration** : `create_all` crée les tables absentes mais ne modifie pas les tables existantes. Après un changement de colonne (ids passés de texte à entier par exemple), supprimer le schéma en local : `DROP SCHEMA search CASCADE;`. Alembic sera nécessaire au premier changement de schéma sur une base qui a des données à garder.

- **Event perdu si le handler échoue** (base indisponible par exemple) : le message est logué en `ERROR` puis abandonné. À traiter avec #11.
- **Format des erreurs 422** : format par défaut de FastAPI. À remplacer par `common.errors` quand #2 sera mergée.
- **Pas de migrations** : le schéma est créé par `create_all` au démarrage, sans Alembic. Une colonne ajoutée plus tard ne sera pas créée sur une base existante.
- **Tri des noms accentués** : `lower()` de SQLite ne traite que l'ASCII, donc l'ordre des noms accentués peut différer entre les tests et Postgres.
- **Trous possibles dans l'index du chat** : un message vu dans le chat peut manquer dans la recherche. Cas connus : broker coupé côté `live-chat` (le message est diffusé sans être publié) ; redémarrage du broker (Mosquitto tourne sans `persistence`, la session et les messages en attente sont perdus) ; `search` coupé longtemps (Mosquitto garde au plus `max_queued_messages`, 1000 par défaut, par session) ; plantage de `search` pendant le traitement (acquittement à la réception) ; handler en échec. `search` ne lit jamais la base de `live-chat`, donc aucun rattrapage n'est possible. La recherche est cohérente à terme : un message envoyé à l'instant peut ne pas être encore indexé.
- **Faux messages possibles** : le broker accepte les connexions anonymes, n'importe quel conteneur peut publier un `chat/message` avec un faux `author_name`. Les ACL du broker sont hors périmètre.
- **Base indisponible : 500** sur les deux routes. Viser 503, dans un ticket transverse. Attention : asyncpg lève alors `ConnectionRefusedError` (un `OSError`), pas `OperationalError`.
- **Recherche littérale** : sous-chaîne exacte du texte normalisé, sans tolérance aux fautes ni recherche par mots.
- **Pas d'index GIN sur les messages** : mesuré, il ne sert ni aux requêtes de 1 ou 2 caractères ni aux termes fréquents ; le pire cas (terme absent, 300 000 messages sur un live) reste autour de 50 ms. Pour l'ajouter plus tard : `create_all` n'ajoute pas d'index à une table existante, il faudra un `CREATE INDEX` à la main ou Alembic.
- **Deux instances avec le même `client_id`** : le broker déconnecte la première quand la seconde se connecte, et elles se volent la session en boucle. Une seule instance de `search` à la fois, ou un `client_id` par instance (avec une session chacune).
- **Garde-fou perdu de `MqttClient._run`** : la boucle de `common` n'attrape que `aiomqtt.MqttError`. Une exception inattendue hors du handler arrête la tâche du client : l'API répond toujours, mais plus aucun event n'est indexé jusqu'au redémarrage de `search`. L'ancien consumer local repartait après n'importe quelle exception.
