# main

Point d'entrée unique du front. `main` gère les comptes utilisateurs et sert de passerelle vers les autres services (`stream`, `live-chat`, `replay`, ...), qui ne sont jamais exposés directement. Les données sont stockées dans PostgreSQL.

```
front ──HTTP──> main ──> PostgreSQL (users)
                  └────> stream, live-chat, replay, ...
```

## Lancer

PostgreSQL doit tourner. Depuis la racine du repo :

    docker compose up -d

Puis, depuis la racine :

    make main

ou depuis `main/` :

    uv run fastapi dev --port 8000

| Variable       | Défaut | Rôle                                                                              |
|----------------|--------|-----------------------------------------------------------------------------------|
| `DATABASE_URL` | aucun  | URL SQLAlchemy de la base, ex. `postgresql+psycopg://postgres:postgres@localhost:5432/microservices`. Obligatoire |

Les variables se mettent dans `main/.env` (copier `.env.example`). Les valeurs de `.env.example` correspondent à celles par défaut du `docker-compose.yml`.

Les tables sont créées au démarrage (`Base.metadata.create_all`) si elles n'existent pas. Il n'y a pas encore de migrations : une table existante n'est jamais modifiée, il faut la supprimer à la main si son modèle change.

## Endpoints

| Chemin           | Protocole | Rôle                                  |
|------------------|-----------|---------------------------------------|
| `/`              | HTTP GET  | Renvoie `{"service": "main"}`         |
| `/health`        | HTTP GET  | Renvoie `{"status": "ok"}`            |
| `/auth/register` | HTTP POST | Crée un compte utilisateur            |

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

Les tests utilisent une base SQLite en mémoire, recréée pour chaque test : ils n'ont pas besoin de PostgreSQL ni de `.env`.

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

## Limites

- Pas encore de connexion ni de jeton : on peut créer un compte mais pas s'authentifier.
- Pas de migrations : les tables sont créées au démarrage, un changement de modèle demande de recréer la table.
- Si PostgreSQL n'est pas prêt quand l'API démarre, le `create_all` échoue et l'API plante : il faut la relancer.
- Le relais vers les autres services n'est pas encore implémenté.
