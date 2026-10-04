# main

Point d'entrée unique du front. `main` sert aussi le build du front (`web/`). `main` gère les comptes utilisateurs et sert de passerelle vers les autres services (`stream`, `live-chat`, `replay`, ...), qui ne sont jamais exposés directement. Les données sont stockées dans PostgreSQL.

```
front ──HTTP──> main ──> PostgreSQL (users)
                  └────> stream, search, live-chat, replay, ...
```

## Lancer

PostgreSQL et le broker MQTT doivent tourner. Depuis la racine du repo :

    docker compose up -d postgres mqtt

Puis, depuis la racine :

    make main

ou depuis `main/` :

    uv run fastapi dev --port 8000

| Variable       | Défaut | Rôle                                                                              |
|----------------|--------|-----------------------------------------------------------------------------------|
| `DATABASE_URL` | aucun  | URL SQLAlchemy de la base, ex. `postgresql+psycopg://postgres:postgres@localhost:5432/microservices`. Obligatoire |
| `JWT_SECRET_KEY` | aucun | Clé qui signe les jetons d'accès. Obligatoire. À générer avec `openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` | Algorithme de signature des jetons |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Durée de validité d'un jeton, en minutes |
| `STREAM_URL` | `http://localhost:8001` | URL du service `stream`, utilisée pour relayer le HLS |
| `STREAM_TIMEOUT_SECONDS` | `5` | Délai maximum d'attente d'une réponse de `stream`, en secondes |
| `SEARCH_URL` | `http://localhost:8004` | URL du service `search`, utilisée pour relayer la recherche |
| `SEARCH_TIMEOUT_SECONDS` | `5` | Délai maximum d'attente d'une réponse de `search`, en secondes |
| `REPLAY_URL` | `http://localhost:8003` | URL du service `replay` |
| `REPLAY_TIMEOUT_SECONDS` | `5` | Délai maximum d'attente d'une réponse de `replay`, en secondes |
| `STATS_URL` | `http://localhost:8006` | URL du service `stats` |
| `STATS_TIMEOUT_SECONDS` | `5` | Délai maximum d'attente d'une réponse de `stats`, en secondes |
| `LIVE_CHAT_URL` | `http://localhost:8002` | URL du service `live-chat`, utilisée pour relayer le chat |
| `LIVE_CHAT_TIMEOUT_SECONDS` | `5` | Délai maximum d'attente d'une réponse de `live-chat`, en secondes |
| `MQTT_HOST` | `localhost` | Hôte du broker MQTT (`mqtt` dans le docker-compose) |
| `MQTT_PORT` | `1883` | Port du broker MQTT |
| `FRONTEND_DIR` | `../web/dist` | Dossier du build du front servi par `main`, relatif à `main/`. S'il n'existe pas, `main` démarre sans front |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Origine du front autorisée à appeler `main` depuis le navigateur (CORS), ex. `https://app.example.com`, sans `/` final |

Les variables se mettent dans `main/.env` (copier `.env.example`). Les valeurs de `.env.example` correspondent à celles par défaut du `docker-compose.yml`. Remplacer `JWT_SECRET_KEY=change-me` par une vraie clé : quiconque la connaît peut fabriquer un jeton valide pour n'importe quel compte.

En image Docker, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f main/Dockerfile -t main .

Les tables sont créées au démarrage (`Base.metadata.create_all`) si elles n'existent pas. Il n'y a pas encore de migrations : une table existante n'est jamais modifiée, il faut la supprimer à la main si son modèle change.

## Endpoints

Toute l'API est sous `/api` (ex. `/api/auth/login`, `ws://localhost:8000/api/streams/{stream_id}/ingest`). Les chemins de cette section sont donnés sans ce préfixe. Les autres URL sont celles du front : `app.frontend()` de FastAPI sert les fichiers de `FRONTEND_DIR`, et renvoie `index.html` à une navigation du navigateur sur une URL inconnue (pour react-router). Une requête `fetch` vers une route inconnue reçoit toujours un `404` JSON.

| Chemin           | Protocole | Rôle                                  |
|------------------|-----------|---------------------------------------|
| `/` (soit `/api`) | HTTP GET  | Renvoie `{"service": "main"}`         |
| `/health`        | HTTP GET  | Renvoie `{"status": "ok"}`            |
| `/auth/register` | HTTP POST | Crée un compte utilisateur            |
| `/auth/login`    | HTTP POST | Connecte un utilisateur, renvoie un jeton JWT |
| `/auth/me`       | HTTP GET  | Renvoie l'utilisateur du jeton (protégé) |
| `/streams`       | HTTP POST | Crée une session de live (protégé)    |
| `/streams`       | HTTP GET  | Liste les sessions, filtrable par statut |
| `/streams/{id}`  | HTTP GET  | Renvoie le détail d'une session       |
| `/streams/{stream_id}/ingest` | WebSocket | Reçoit le flux vidéo du streamer et le relaie à `stream` (jeton en query) |
| `/streams/{stream_id}/chat` | WebSocket | Relaie le chat du live avec `live-chat` dans les deux sens (jeton facultatif en query, sans jeton : lecture seule) |
| `/lives/{stream_id}/{filename}` | HTTP GET | Relaie la playlist ou un segment HLS d'un live depuis `stream` |
| `/search` | HTTP GET | Cherche des streamers et des messages du chat de tous les lives via `search` |

La doc interactive est sur `http://localhost:8000/api/docs`.

### `POST /auth/register`

Corps JSON :

```json
{"username": "John_Doe", "password": "MyPassword123"}
```

| Champ      | Contraintes                                                 |
|------------|-------------------------------------------------------------|
| `username` | 3 à 30 caractères, lettres, chiffres et `_` uniquement. Unique sans tenir compte de la casse |
| `password` | 8 caractères minimum                                        |

Réponses :

| Code  | Quand                                                                 |
|-------|-----------------------------------------------------------------------|
| `201` | Compte créé. Renvoie un `UserResponse` : `{"id": 1, "username": "john_doe", "display_name": "John_Doe", "role": "user"}` |
| `409` | Le `username` est déjà pris, quelle que soit la casse (`Username already registered`) |
| `422` | Corps invalide (champ manquant, trop court, caractère interdit, ...)  |

Le mot de passe n'est jamais stocké en clair : il est haché avec Argon2id via [pwdlib](https://frankie567.github.io/pwdlib/) (`PasswordHash.recommended()`, comme dans le [tuto sécurité de FastAPI](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#hash-and-verify-the-passwords)). La chaîne stockée contient l'algorithme, les paramètres, le sel et le hash (ex. `$argon2id$v=19$m=65536,t=3,p=4$<sel>$<hash>`) : si on change les paramètres, les anciens mots de passe restent vérifiables. Tout nouveau compte a le rôle `user`.

La réponse est filtrée par le schéma `UserResponse` (`response_model`) : seuls ses champs sont renvoyés, jamais `hashed_password`.

Le `username` est l'identifiant : il est enregistré en minuscules, donc `alice` et `Alice` sont le même compte (le second reçoit `409`). L'orthographe saisie est gardée dans `display_name`, c'est elle qu'on affiche (chat, profil, ...).

### `POST /auth/login`

Suit le [tuto OAuth2 + JWT de FastAPI](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/). Le corps est un **formulaire** (`application/x-www-form-urlencoded`), pas du JSON, comme l'impose le flux OAuth2 « password » :

    username=john_doe&password=MyPassword123

Le `username` n'est pas sensible à la casse (`John_Doe` et `john_doe` se connectent au même compte).

Réponses :

| Code  | Quand                                                                 |
|-------|-----------------------------------------------------------------------|
| `200` | Identifiants valides. Renvoie `{"access_token": "<jwt>", "token_type": "bearer"}` |
| `401` | `username` inconnu ou mauvais mot de passe (`Incorrect username or password`), avec l'en-tête `WWW-Authenticate: Bearer` |
| `422` | Champ manquant, ou corps envoyé en JSON au lieu d'un formulaire       |

Un `username` qui ne respecte pas les règles de l'inscription (longueur, caractères autorisés) ne peut correspondre à aucun compte : il reçoit directement `401` sans que la base soit interrogée. Sans ça, un caractère que PostgreSQL refuse (octet NUL, `%00`) provoquerait une `500`.

Le message d'erreur est le même que le compte existe ou non. Si le `username` est inconnu, on vérifie quand même le mot de passe contre un hash factice (`DUMMY_HASH`) pour que la réponse prenne le même temps : on ne peut pas deviner les pseudos existants en mesurant le temps de réponse.

Le jeton est un JWT signé avec `JWT_SECRET_KEY` (PyJWT, `HS256` par défaut). Son contenu :

| Claim | Valeur                                                          |
|-------|-----------------------------------------------------------------|
| `sub` | `username` du compte (en minuscules)                            |
| `exp` | Date d'expiration, `ACCESS_TOKEN_EXPIRE_MINUTES` après la connexion |

Les deux claims sont obligatoires : un jeton sans `exp` ou sans `sub` est refusé (`401`). Sans ça, PyJWT ne vérifie `exp` que s'il est présent, et un jeton sans `exp` n'expirerait jamais.

Il n'est pas chiffré (n'importe qui peut lire son contenu), seulement signé : il ne contient donc rien de secret.

### `GET /auth/me`

Route protégée : il faut envoyer le jeton dans l'en-tête `Authorization: Bearer <access_token>`.

| Code  | Quand                                                                 |
|-------|-----------------------------------------------------------------------|
| `200` | Renvoie le `UserResponse` du compte connecté                          |
| `401` | Jeton absent (`Not authenticated`), invalide, expiré, signé avec une autre clé, ou dont le compte n'existe plus (`Could not validate credentials`) |

### Sessions de live

Chaque clic sur « Go live » crée une session avec un identifiant unique, utilisé ensuite dans l'URL d'ingestion. Un `Stream` ressemble à :

```json
{
  "id": 1,
  "streamer": {"id": 3, "username": "john_doe"},
  "title": "Speedrun any%",
  "game": "Celeste",
  "status": "created",
  "created_at": "2026-10-01T18:00:00Z",
  "started_at": null,
  "ended_at": null
}
```

Statuts : `created` (session créée, rien reçu), `live`, `ended`, `cancelled` (restée `created` plus de 10 minutes).

`POST /streams` (protégé) :

| Champ   | Contraintes       |
|---------|-------------------|
| `title` | 1 à 100 caractères |
| `game`  | 1 à 50 caractères  |

| Code | Cas |
|------|-----|
| 201  | Session créée, statut `created` |
| 401  | Jeton absent ou invalide |
| 409  | Le streamer a déjà une session `created` ou `live` |
| 422  | Titre ou jeu invalide |

Une session `created` depuis plus de 10 minutes sans ingestion est passée en `cancelled` au moment où son streamer en crée une nouvelle, ce qui libère la place. Le même nettoyage est fait à chaque `GET /streams`, pour ne pas lister de sessions abandonnées. Un index unique partiel en base garantit une seule session `created` ou `live` par streamer, même avec deux requêtes simultanées.

`GET /streams?status=live&page=1&size=20` renvoie `{"items": [...], "total", "page", "size"}`, les plus récentes d'abord. `status` est optionnel (`created`, `live`, `ended`, `cancelled`), `size` va de 1 à 100. Pas besoin d'être connecté.

`GET /streams/{id}` renvoie la session, ou 404.

Le passage en `live` et en `ended` se fait dans `app/services/streams.py` (`mark_started`, `mark_ended`), appelés par l'ingest (premier morceau relayé, refus définitif de `stream` via `mark_over`) et par les events MQTT `stream/started` et `stream/ended` (voir « Events MQTT »). `mark_started` n'agit que sur une session `created`, `mark_ended` que sur une session `live` : tout autre appel est ignoré.

### `WS /streams/{stream_id}/ingest?token=<jwt>`

Le navigateur du streamer envoie des morceaux WebM en binaire. `main` vérifie le jeton et que le streamer est bien le propriétaire de la session, puis ouvre une WebSocket vers `stream` (`/streams/{stream_id}/ingest`, avec `streamer_id`, `streamer_name`, `title` et `game` en query) et recopie chaque morceau sans le modifier.

```
streamer --WebSocket--> main (auth) --WebSocket--> stream --stdin--> ffmpeg
```

Les refus sont envoyés après l'ouverture de la connexion : avant, le navigateur ne recevrait qu'un 403 HTTP et perdrait le code.

| Code de fermeture | Cas |
|-------------------|-----|
| Code de fermeture | Cas | Que faire côté front |
|-------------------|-----|----------------------|
| 4401 | Jeton absent ou invalide (un jeton absent de l'URL est refusé par un 403 HTTP) | Se reconnecter |
| 4403 | La session appartient à un autre streamer | - |
| 4404 | La session n'existe pas | - |
| 4409 | La session est terminée : `ended` ou `cancelled` en base, ou `stream` ne l'accepte plus (`Stream id already used`, ou `stream` a redémarré) | Créer une nouvelle session (`POST /streams`) |
| 4423 | Une autre connexion diffuse déjà sur cette session (`Stream already live` côté `stream`) | Fermer l'autre onglet ou attendre |
| 1003 | Le streamer a envoyé un message texte au lieu de binaire | - |
| 1013 | `stream` n'a rien reçu pendant `SIGNAL_TIMEOUT_SECONDS` : c'est une coupure, pas la fin du live | Se reconnecter sur la **même** session avant `RECONNECT_SECONDS` |
| 1011 | `stream` est injoignable, ffmpeg a planté, ou autre fermeture inattendue. La raison est reprise dans le message de fermeture | Réessayer |

Quand le streamer se déconnecte, la connexion vers `stream` est fermée proprement. Une session `live` peut être rouverte : c'est la reconnexion du streamer pendant la période de grâce de `stream`.

`main` traduit les codes de fermeture de `stream` (voir `stream/README.md`) :

| `stream` envoie | `main` envoie | Effet sur la session |
|-----------------|---------------|----------------------|
| `1008` `Stream id already used` | `4409` | `live` → `ended` (`ended_at` = maintenant), `created` → `cancelled` |
| `1012` (redémarrage, le live est terminé) | `4409` | Pareil |
| `1008` `Stream already live` | `4423` | Aucun |
| `1013` `No data received` | `1013` | Aucun, la session reste `live` |
| `1011` ou autre | `1011` | Aucun |

Sur `4409`, `main` termine la session sans attendre `stream/ended` : si cet event a été perdu (broker coupé), la session ne reste pas bloquée en `live` et le streamer peut en créer une nouvelle. Si `stream/ended` arrive ensuite, il est ignoré (la session n'est plus `live`). Les deux cas de `1008` ne se distinguent que par leur raison : `main` compare le texte exact envoyé par `stream`.

Dès le premier morceau relayé à `stream`, la session passe de `created` à `live` (avec l'heure de `main`) : une session qui diffuse n'est donc pas annulée par le nettoyage des 10 minutes. `stream/started` remplace ensuite `started_at` par l'heure où ffmpeg a démarré (voir « Events MQTT »). Les messages texte sont refusés (`1003`). Les accès à la base pendant le relais se font dans un thread (`asyncio.to_thread`), pour ne pas bloquer les autres connexions.

### `GET /lives/{stream_id}/{filename}`

`main` appelle `stream` et renvoie sa réponse telle quelle, pour que le player hls.js du front ne contacte jamais `stream` directement. Pas besoin d'être connecté pour regarder.

| Fichier        | Type                                | `Cache-Control`           |
|----------------|-------------------------------------|---------------------------|
| `index.m3u8`   | `application/vnd.apple.mpegurl`     | `no-cache` (la playlist change pendant le live) |
| `index{N}.ts`  | `video/mp2t`                        | `public, max-age=3600`    |

`filename` doit respecter `^index\d*\.(m3u8|ts)$`, sinon 422 : impossible de sortir du dossier du live. Les segments sont relayés en streaming, sans être chargés entièrement en mémoire.

| Code | Cas |
|------|-----|
| 200  | Fichier relayé |
| 404  | Live ou fichier inexistant (réponse de `stream` renvoyée telle quelle) |
| 422  | `stream_id` ou `filename` invalide |
| 502  | `stream` a renvoyé une réponse inattendue |
| 503  | `stream` est injoignable |
| 504  | `stream` n'a pas répondu à temps |

Les erreurs viennent du helper commun, voir « Appeler un satellite ».

### `GET /search?q=`

Une seule barre de recherche, une seule route : `main` interroge `search` (voir `search/README.md`) et assemble la réponse. Pas besoin d'être connecté.

`q` est obligatoire et fait 2 à 100 caractères une fois les espaces du début et de la fin retirés. Sinon `main` répond 422 sans appeler `search`.

Les deux appels à `search` partent en parallèle :

| Section     | Appel à `search`            | Contenu |
|-------------|-----------------------------|---------|
| `streamers` | `GET /search/streamers?q=`  | Les 20 premiers streamers trouvés, en live d'abord |
| `messages`  | `GET /search/messages?q=`   | Les messages du chat de tous les lives qui contiennent `q` (#150) |

```json
{
  "streamers": [{"streamer_id": 42, "streamer_name": "Célèste", "last_title": "Speedrun any%", "last_game": "Celeste", "is_live": true, "live_stream_id": 7}],
  "messages": [{"message_id": "3f2b8d6a-7c1e-4a95-b0d4-6e8f1a2c5b97", "stream_id": 7, "author_name": "Célèste", "content": "GG WP !", "sent_at": "2026-10-02T20:14:03Z"}]
}
```

| Code | Cas |
|------|-----|
| 200  | Toujours, dès que `q` est valide. Une section dont l'appel échoue (`search` injoignable, trop lent, code autre que 200, réponse invalide) revient vide et l'erreur est journalisée ; l'autre section est quand même renvoyée |
| 422  | `q` absent, ou de moins de 2 ou plus de 100 caractères après retrait des espaces. `search` n'est pas appelé |

Tant que #150 n'est pas mergé, `search` répond 404 sur `/search/messages` : `messages` est toujours vide, et se remplira sans changement côté `main` après le merge.

Un `q` que `search` refuse alors que `main` l'accepte (vide après normalisation, par exemple des accents seuls) donne aussi des sections vides.

### Appeler un satellite

Chaque satellite a son `httpx.AsyncClient`, créé dans le `lifespan` avec l'URL et le timeout de `.env`, et sa dépendance : `get_stream_client`, `get_search_client`, `get_replay_client`, `get_stats_client` (`app/dependencies.py`).

`app/services/satellites.py` fait l'appel et traite les erreurs une seule fois pour toutes les routes :

```python
from app.dependencies import get_optional_user, get_replay_client
from app.services import satellites

REPLAYS = TypeAdapter(list[Replay])

async def list_replays(client: httpx.AsyncClient, user: User | None) -> list[Replay]:
    response = await satellites.send(client, "GET", "/replays", user=user)
    return satellites.parse(response, REPLAYS)
```

- `send(client, method, path, *, user=None, params=None, json=None, stream=False)` renvoie la réponse si son code est 2xx. Avec `stream=True`, le corps n'est pas chargé en mémoire (relais HLS) : penser à fermer la réponse
- `parse(response, adapter)` valide le corps JSON avec un `TypeAdapter`
- Avec un `user`, les headers `X-User-Id`, `X-User-Name` (`username`, en minuscules) et `X-User-Role` de `common.identity` sont ajoutés. Pour une route publique qui veut quand même les envoyer quand l'utilisateur est connecté, la dépendance `get_optional_user` renvoie le `User`, ou `None` sans jeton (un jeton invalide reste un `401`)

Les erreurs sont des exceptions, transformées en réponse par les handlers de `app/main.py` : la route n'a rien à attraper.

| Le satellite                         | Exception                       | `main` renvoie |
|--------------------------------------|---------------------------------|----------------|
| répond 4xx                           | `SatelliteRejectedError`        | La même réponse : code, corps et `Content-Type` (Starlette ajoute `; charset=utf-8` à un type `text/*` qui n'a pas de charset) |
| répond un autre code (3xx, 5xx)      | `InvalidSatelliteResponseError` | `502 {"detail": "Invalid answer from service"}` |
| renvoie un corps refusé par `parse`  | `InvalidSatelliteResponseError` | `502 {"detail": "Invalid answer from service"}` |
| est injoignable                      | `SatelliteUnavailableError`     | `503 {"detail": "Service is unavailable"}` |
| ne répond pas avant le timeout       | `SatelliteTimeoutError`         | `504 {"detail": "Service timed out"}` |

Toutes héritent de `SatelliteError`, pour une route qui veut les traiter elle-même (la recherche renvoie une section vide, par exemple). Le détail (URL, code reçu) est journalisé, il n'est pas renvoyé au front.

### Protéger une route

La dépendance `get_current_user` (`app/dependencies.py`) lit le jeton, le vérifie et renvoie le `User` correspondant, ou répond `401`. Pour protéger une route :

```python
from app.dependencies import get_current_user

@router.get("/quelque-chose")
def quelque_chose(current_user: Annotated[User, Depends(get_current_user)]):
    ...
```

Pour une route réservée aux admins (les futures routes `/stats`, par exemple), utiliser `require_admin` à la place. Elle fait la même vérification, puis répond `403` (`Admin role required`) si le rôle du compte n'est pas `admin` :

```python
from app.dependencies import require_admin

@router.get("/stats")
def stats(admin: Annotated[User, Depends(require_admin)]):
    ...
```

Dans la doc interactive (`/docs`), le bouton **Authorize** permet de se connecter avec un `username` / `password` : Swagger appelle `/auth/login` et envoie ensuite le jeton sur les routes protégées.

### Créer un admin

Tout compte créé par `/auth/register` a le rôle `user`. Pour donner le rôle `admin` à un compte existant, depuis `main/` (avec le même `DATABASE_URL` que l'API) :

    uv run python -m app.scripts.make_admin john_doe

Dans l'image Docker, ajouter `--no-dev` (les dépendances de dev n'y sont pas installées) :

    uv run --no-dev python -m app.scripts.make_admin john_doe

Le `username` n'est pas sensible à la casse. Le script affiche `john_doe is now admin`, ou `User 'john_doe' not found` (code de sortie `1`) si le compte n'existe pas. Le rôle est lu en base à chaque requête : le jeton déjà obtenu par le compte devient admin tout de suite, sans reconnexion. `GET /auth/me` renvoie le rôle dans le champ `role`.

## Events MQTT

Au démarrage, `main` se connecte au broker avec le `MqttClient` de `common` (`app/mqtt.py`). La connexion se fait en tâche de fond : si le broker est absent, l'API démarre quand même et réessaie toutes les 5 s.

| Topic            | Event           | Effet                                                      |
|------------------|-----------------|------------------------------------------------------------|
| `stream/started` | `StreamStarted` | `record_started` : le stream passe de `created` à `live`, `started_at` est rempli. S'il est déjà `live` (passé en `live` par l'ingest au premier morceau), `started_at` est remplacé par celui de l'event : c'est `stream` qui fait foi |
| `stream/ended`   | `StreamEnded`   | `mark_ended` : le stream passe de `live` à `ended`, `ended_at` est rempli |

Les handlers sont dans `app/services/streams.py`. Chaque event ouvre sa propre session et tourne dans un thread (`asyncio.to_thread`), car la base est synchrone et ne doit pas bloquer la boucle. Un event pour un stream inconnu est ignoré et journalisé. Un event en retard ou en double ne change rien : `stream/started` n'agit que sur un stream `created` ou `live`, `stream/ended` que sur un stream `live`.

Le client est aussi dans `app.state.mqtt` pour publier depuis une route.

## Base de données

Table `users` :

| Colonne           | Type          | Notes                                  |
|-------------------|---------------|----------------------------------------|
| `id`              | int           | Clé primaire                           |
| `username`        | varchar(30)   | En minuscules. Unique, indexé          |
| `display_name`    | varchar(30)   | Pseudo tel que saisi à l'inscription   |
| `hashed_password` | varchar(255)  | Hash Argon2id (format PHC, via pwdlib) |
| `role`            | varchar(20)   | `user` (par défaut) ou `admin`         |
| `created_at`      | timestamptz   | Rempli par la base                     |
| `updated_at`      | timestamptz   | Mis à jour par SQLAlchemy à chaque modification |

## Tester

### Tests automatiques

    cd main
    uv run pytest

Les tests utilisent une base SQLite en mémoire, recréée pour chaque test : ils n'ont pas besoin de PostgreSQL, ni de broker MQTT, ni de `.env`.

### À la main

Avec le service lancé :

    # créer un compte : username "john_doe", display_name "John_Doe"
    curl -i -X POST http://localhost:8000/api/auth/register \
      -H 'Content-Type: application/json' \
      -d '{"username": "John_Doe", "password": "MyPassword123"}'

    # le même pseudo, même avec une autre casse, renvoie 409
    curl -i -X POST http://localhost:8000/api/auth/register \
      -H 'Content-Type: application/json' \
      -d '{"username": "john_doe", "password": "MyPassword123"}'

    # se connecter (formulaire, pas JSON) et garder le jeton
    TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
      -d 'username=john_doe&password=MyPassword123' | jq -r .access_token)

    # route protégée : 200 avec le jeton, 401 sans
    curl -i http://localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN"
    curl -i http://localhost:8000/api/auth/me

    # mauvais mot de passe : 401
    curl -i -X POST http://localhost:8000/api/auth/login \
      -d 'username=john_doe&password=wrong-password'

## Limites

- Pas de refresh token ni de déconnexion : un jeton reste valide jusqu'à son expiration, même après un « logout » côté front. Le front doit se reconnecter quand il reçoit un `401`.
- Pas de limite sur le nombre de tentatives de connexion (pas de protection contre le brute force).
- `require_admin` n'est branché sur aucune route : les routes `/stats` n'existent pas encore.
- Pas de route pour retirer le rôle `admin` : il faut modifier la colonne `role` en base.
- Pas de migrations : les tables sont créées au démarrage, un changement de modèle demande de recréer la table.
- Si PostgreSQL n'est pas prêt quand l'API démarre, le `create_all` échoue et l'API plante : il faut la relancer.
- Seuls `stream` (ingest et HLS), `search` et le chat de `live-chat` sont relayés : le relais vers `replay`, ... n'est pas encore implémenté.
- Les ids de session viennent de l'auto-incrément PostgreSQL, et `stream` refuse un id dont le dossier `lives/{stream_id}/` existe déjà (`Stream id already used`). Si la base est vidée (volume `postgres-data` supprimé) sans vider `stream/lives/`, les nouvelles sessions reprennent à 1 et leurs lives sont refusés : il faut vider les deux ensemble.
