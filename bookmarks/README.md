# bookmarks

Bookmarks des utilisateurs : un utilisateur enregistre un streamer ou un replay avec un label et une note (#91), puis liste et relit ses bookmarks (#92). Chaque suppression réussie est publiée sur `bookmarks/deleted` pour `stats` (#117). Le service n'est jamais exposé au front : tout passe par `main`, qui authentifie l'utilisateur et transmet son identité.

```
front ──> main ──HTTP /bookmarks + X-User-*──> bookmarks ──> Postgres, table bookmark
                                                   └──MQTT bookmarks/deleted──> stats
```

## Lancer

PostgreSQL doit tourner (le service ne démarre pas sans). Depuis la racine du repo :

    make infra-up
    make bookmarks

ou depuis `bookmarks/` :

    uv run fastapi dev --port 8005

En image Docker, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f bookmarks/Dockerfile -t bookmarks .

Au démarrage, le service crée sa table si elle n'existe pas, puis se connecte au broker. Sans broker, le service démarre quand même : le client MQTT réessaie de se connecter toutes les 5 secondes.

## Configuration

Les variables se mettent dans `bookmarks/.env` (copier `.env.example`).

| Variable       | Défaut                                                                | Rôle                |
|----------------|-----------------------------------------------------------------------|---------------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/microservices` | Base Postgres       |
| `MQTT_HOST`    | `localhost`                                                           | Hôte du broker MQTT |
| `MQTT_PORT`    | `1883`                                                                | Port du broker MQTT |

## Identité

`bookmarks` ne vérifie aucun jeton : `main` l'a déjà fait, et transmet l'utilisateur dans trois headers lus par `CurrentUser` de `common` :

| Header        | Exemple   |
|---------------|-----------|
| `X-User-Id`   | `42`      |
| `X-User-Name` | `alice`   |
| `X-User-Role` | `user`    |

Sans ces headers (ou avec un `X-User-Id` invalide), toutes les routes `/bookmarks` répondent `401`. Un utilisateur ne voit et ne modifie que ses propres bookmarks : le bookmark d'un autre répond `404`, comme un bookmark qui n'existe pas.

Pour tester sans `main` :

    curl http://localhost:8005/bookmarks \
      -H "X-User-Id: 1" -H "X-User-Name: alice" -H "X-User-Role: user"

## Endpoints

| Chemin                    | Méthode | Rôle                                         |
|---------------------------|---------|----------------------------------------------|
| `/health`                 | GET     | Renvoie `{"status": "ok"}`                   |
| `/bookmarks`              | POST    | Crée un bookmark (`201`, header `Location`)  |
| `/bookmarks`              | GET     | Liste paginée des bookmarks de l'utilisateur |
| `/bookmarks/{id}`         | GET     | Détail d'un bookmark                         |
| `/bookmarks/{id}`         | PATCH   | Modifie le label et/ou la note               |
| `/bookmarks/{id}`         | DELETE  | Supprime un bookmark (`204`), publie l'event |

### Règles de validation

Toute violation répond `422`, et un champ inconnu aussi (`extra="forbid"`).

| Champ         | Règle |
|---------------|-------|
| `target_type` | `streamer` ou `replay` |
| `target_id`   | entier strict (pas `"9"` ni `10.0`), de 1 à 2³¹ − 1 |
| `label`       | obligatoire à la création, 1 à 100 caractères après suppression des espaces autour, jamais `null`, pas de caractère nul |
| `note`        | optionnelle, 1 à 300 caractères après suppression des espaces autour, pas de caractère nul. `null` dans un `PATCH` efface la note |
| `{id}`        | de 1 à 2³¹ − 1 |

Un même utilisateur ne peut pas bookmarker deux fois la même cible (`target_type`, `target_id`) : `409`. Deux utilisateurs différents le peuvent.

Le `PATCH` est partiel : seuls les champs envoyés sont modifiés.

### `GET /bookmarks`

| Param         | Défaut | Rôle |
|---------------|--------|------|
| `target_type` | aucun  | `streamer` ou `replay` pour ne garder qu'un type |
| `page`        | `1`    | Numéro de page, à partir de 1 |
| `size`        | `20`   | Taille de page, de 1 à 100 |

La réponse suit le format `Page` de `common` ; `total` compte tous les bookmarks qui correspondent au filtre, pas seulement ceux de la page. Les bookmarks sont triés du plus récent au plus ancien (`created_at` puis `id`), un ordre stable d'une page à l'autre.

```json
{"items": [{"id": 3, "user_id": 1, "target_type": "streamer", "target_id": 42, "label": "Mon streamer", "note": null, "created_at": "...", "updated_at": "..."}], "total": 1, "page": 1, "size": 20}
```

## Event `bookmarks/deleted`

Après chaque suppression réussie, `bookmarks` publie un `BookmarkDeleted` (modèle dans `common.events`) :

| Champ         | Rôle |
|---------------|------|
| `bookmark_id` | Id du bookmark supprimé |
| `user_id`     | Utilisateur qui l'a supprimé |
| `target_type` | `streamer` ou `replay` |
| `target_id`   | Id de la cible |
| `deleted_at`  | Date de suppression (UTC) |

Un `404` ne publie rien. La publication se fait en tâche de fond (`BackgroundTasks`), après l'envoi de la réponse : le client n'attend jamais le broker, et une suppression réussit même si le broker est coupé.

Si le client MQTT n'est pas connecté (juste après le démarrage, pendant une reconnexion, broker coupé), la publication est retentée jusqu'à 10 fois, toutes les 5 secondes, ce qui couvre une reconnexion du client. Au-delà, l'event est perdu et une erreur est journalisée. Il est aussi perdu si `bookmarks` s'arrête pendant les tentatives, car l'event n'existe qu'en mémoire. Les compteurs de `stats` peuvent donc être légèrement sous-estimés : compromis accepté, la suppression passant avant la statistique. Des comptes exacts demanderaient une outbox (event enregistré dans la même transaction que la suppression, publié ensuite).

## Tests

    uv run pytest

Les tests n'ont besoin ni de Postgres ni de Mosquitto : ils tournent sur SQLite en mémoire, et le client MQTT est remplacé par un `AsyncMock`. Ils vérifient l'event publié (topic et champs), l'absence d'event sur un `404`, et le retry quand le broker est coupé ou revient.
