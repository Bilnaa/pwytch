# main

Point d'entrée unique du front. `main` gère les comptes utilisateurs et sert de passerelle vers les autres services (`stream`, `live-chat`, `replay`, ...), qui ne sont jamais exposés directement. Les données sont stockées dans PostgreSQL.

```
front ──HTTP──> main ──> PostgreSQL (users)
                  └────> stream, live-chat, replay, ...
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
| `MQTT_HOST` | `localhost` | Hôte du broker MQTT (`mqtt` dans le docker-compose) |
| `MQTT_PORT` | `1883` | Port du broker MQTT |

Les variables se mettent dans `main/.env` (copier `.env.example`). Les valeurs de `.env.example` correspondent à celles par défaut du `docker-compose.yml`. Remplacer `JWT_SECRET_KEY=change-me` par une vraie clé : quiconque la connaît peut fabriquer un jeton valide pour n'importe quel compte.

En image Docker, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f main/Dockerfile -t main .

Les tables sont créées au démarrage (`Base.metadata.create_all`) si elles n'existent pas. Il n'y a pas encore de migrations : une table existante n'est jamais modifiée, il faut la supprimer à la main si son modèle change.

## Endpoints

| Chemin           | Protocole | Rôle                                  |
|------------------|-----------|---------------------------------------|
| `/`              | HTTP GET  | Renvoie `{"service": "main"}`         |
| `/health`        | HTTP GET  | Renvoie `{"status": "ok"}`            |
| `/auth/register` | HTTP POST | Crée un compte utilisateur            |
| `/auth/login`    | HTTP POST | Connecte un utilisateur, renvoie un jeton JWT |
| `/auth/me`       | HTTP GET  | Renvoie l'utilisateur du jeton (protégé) |
| `/streams`       | HTTP POST | Crée une session de live (protégé)    |
| `/streams`       | HTTP GET  | Liste les sessions, filtrable par statut |
| `/streams/{id}`  | HTTP GET  | Renvoie le détail d'une session       |
| `/streams/{stream_id}/ingest` | WebSocket | Reçoit le flux vidéo du streamer et le relaie à `stream` (jeton en query) |
| `/lives/{stream_id}/{filename}` | HTTP GET | Relaie la playlist ou un segment HLS d'un live depuis `stream` |

La doc interactive est sur `http://localhost:8000/docs`.

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

Le passage en `live` et en `ended` est prêt dans `app/services/streams.py` (`mark_started`, `mark_ended`) mais rien ne l'appelle encore (`mark_started` n'agit que sur une session `created`, `mark_ended` que sur une session `live`, tout autre événement est ignoré) : il faudra les brancher sur `stream/started` et `stream/ended` quand #11 (MQTT) sera faite.

### `WS /streams/{stream_id}/ingest?token=<jwt>`

Le navigateur du streamer envoie des morceaux WebM en binaire. `main` vérifie le jeton et que le streamer est bien le propriétaire de la session, puis ouvre une WebSocket vers `stream` (`/streams/{stream_id}/ingest`, avec `streamer_id`, `streamer_name`, `title` et `game` en query) et recopie chaque morceau sans le modifier.

```
streamer --WebSocket--> main (auth) --WebSocket--> stream --stdin--> ffmpeg
```

Les refus sont envoyés après l'ouverture de la connexion : avant, le navigateur ne recevrait qu'un 403 HTTP et perdrait le code.

| Code de fermeture | Cas |
|-------------------|-----|
| 4401 | Jeton absent ou invalide (un jeton absent de l'URL est refusé par un 403 HTTP) |
| 4403 | La session appartient à un autre streamer |
| 4404 | La session n'existe pas |
| 4409 | La session est `ended` ou `cancelled` |
| 1003 | Le streamer a envoyé un message texte au lieu de binaire |
| 1011 | `stream` est injoignable, a coupé la connexion ou l'a refusée (ex. `Stream already live`). La raison est reprise dans le message de fermeture |

Quand le streamer se déconnecte, la connexion vers `stream` est fermée proprement. Une session `live` peut être rouverte : c'est la reconnexion du streamer pendant la période de grâce de `stream`.

Dès le premier morceau relayé à `stream`, la session passe de `created` à `live` : une session qui diffuse n'est donc pas annulée par le nettoyage des 10 minutes. Les messages texte sont refusés (`1003`). Après un `1013` envoyé par `stream` (rien reçu pendant `SIGNAL_TIMEOUT_SECONDS`), le streamer reçoit un `1011` et doit rouvrir la connexion.

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
| 404  | Live ou fichier inexistant |
| 422  | `stream_id` ou `filename` invalide |
| 502  | `stream` a renvoyé une réponse inattendue |
| 503  | `stream` est injoignable |
| 504  | `stream` n'a pas répondu à temps |

### Protéger une route

La dépendance `get_current_user` (`app/dependencies.py`) lit le jeton, le vérifie et renvoie le `User` correspondant, ou répond `401`. Pour protéger une route :

```python
from app.dependencies import get_current_user

@router.get("/quelque-chose")
def quelque_chose(current_user: Annotated[User, Depends(get_current_user)]):
    ...
```

Dans la doc interactive (`/docs`), le bouton **Authorize** permet de se connecter avec un `username` / `password` : Swagger appelle `/auth/login` et envoie ensuite le jeton sur les routes protégées.

## Events MQTT

Au démarrage, `main` se connecte au broker avec le `MqttClient` de `common` (`app/mqtt.py`). La connexion se fait en tâche de fond : si le broker est absent, l'API démarre quand même et réessaie toutes les 5 s.

| Topic            | Event           | Effet                                                      |
|------------------|-----------------|------------------------------------------------------------|
| `stream/started` | `StreamStarted` | `mark_started` : le stream passe de `created` à `live`, `started_at` est rempli |
| `stream/ended`   | `StreamEnded`   | `mark_ended` : le stream passe de `live` à `ended`, `ended_at` est rempli |

Les handlers sont dans `app/services/streams.py`. Chaque event ouvre sa propre session et tourne dans un thread (`asyncio.to_thread`), car la base est synchrone et ne doit pas bloquer la boucle. Un event pour un stream inconnu est ignoré et journalisé. Un event en retard ou en double ne change rien : `stream/started` n'agit que sur un stream `created`, `stream/ended` que sur un stream `live`.

Le client est aussi dans `app.state.mqtt` pour publier depuis une route.

## Base de données

Table `users` :

| Colonne           | Type          | Notes                                  |
|-------------------|---------------|----------------------------------------|
| `id`              | int           | Clé primaire                           |
| `username`        | varchar(30)   | En minuscules. Unique, indexé          |
| `display_name`    | varchar(30)   | Pseudo tel que saisi à l'inscription   |
| `hashed_password` | varchar(255)  | Hash Argon2id (format PHC, via pwdlib) |
| `role`            | varchar(20)   | `user` par défaut                      |
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
    curl -i -X POST http://localhost:8000/auth/register \
      -H 'Content-Type: application/json' \
      -d '{"username": "John_Doe", "password": "MyPassword123"}'

    # le même pseudo, même avec une autre casse, renvoie 409
    curl -i -X POST http://localhost:8000/auth/register \
      -H 'Content-Type: application/json' \
      -d '{"username": "john_doe", "password": "MyPassword123"}'

    # se connecter (formulaire, pas JSON) et garder le jeton
    TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
      -d 'username=john_doe&password=MyPassword123' | jq -r .access_token)

    # route protégée : 200 avec le jeton, 401 sans
    curl -i http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
    curl -i http://localhost:8000/auth/me

    # mauvais mot de passe : 401
    curl -i -X POST http://localhost:8000/auth/login \
      -d 'username=john_doe&password=wrong-password'

## Limites

- Pas de refresh token ni de déconnexion : un jeton reste valide jusqu'à son expiration, même après un « logout » côté front. Le front doit se reconnecter quand il reçoit un `401`.
- Pas de limite sur le nombre de tentatives de connexion (pas de protection contre le brute force).
- Le rôle n'est pas encore utilisé pour restreindre l'accès aux routes.
- Pas de migrations : les tables sont créées au démarrage, un changement de modèle demande de recréer la table.
- Si PostgreSQL n'est pas prêt quand l'API démarre, le `create_all` échoue et l'API plante : il faut la relancer.
- Le relais vers les autres services n'est pas encore implémenté.
