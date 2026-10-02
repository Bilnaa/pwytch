# Plan — US live-chat (salon de discussion WebSocket par live)

> En tant que viewer connecté, je veux discuter en temps réel dans le chat d'un live,
> afin d'échanger avec le streamer et les autres viewers.

Architecture retenue : le front passe par `main` (#38), qui vérifie l'identité et la
transmet à `live-chat` en query params (`user_id`, `username`). `live-chat` n'est pas
exposé au front.

---

## Critères d'acceptation

- [x] WebSocket `/streams/{stream_id}/chat` (query params facultatifs `user_id`, `username`)
- [x] Chaque live a son propre salon ; un message est reçu par tous les clients du même live, et seulement eux
- [ ] Message diffusé : `id`, `stream_id`, `author` (`id`, `username`), `content`, `sent_at`
- [ ] Client sans `user_id` ne peut pas écrire (`READ_ONLY`)
- [ ] Message vide (après strip) ou > 500 caractères refusé, erreur explicite, connexion conservée
- [ ] JSON invalide refusé, erreur explicite, connexion conservée
- [ ] La déconnexion d'un client ne perturbe pas les autres
- [ ] Messages persistés en base **avant** diffusion
- [ ] Anti-spam : 1 message / seconde max par utilisateur (`RATE_LIMITED`)
- [ ] Tests automatisés (`tests/test_live_chat.py`)

---

## Feuille de route

| # | Étape | Statut |
|---|---|---|
| 1 | WebSocket minimale (router branché, `accept`, écho) | ✅ fait |
| 2 | `ConnectionManager` (`connect`, `broadcast`, instance partagée) | ✅ fait |
| 3 | Déconnexion (`disconnect` + `try`/`except WebSocketDisconnect`) | 🚧 en cours |
| 4 | Validation (JSON invalide, vide / > 500, `READ_ONLY`) | ⏳ |
| 5 | Format du message diffusé (`id`, `stream_id`, `author`, `content`, `sent_at`) | ⏳ |
| 6 | Anti-spam 1 msg/s par utilisateur (`RATE_LIMITED`) | ⏳ |
| 7 | Persistance Postgres avant diffusion (l'`id` vient de la base) | ⏳ |
| 8 | Tests pytest pour chaque critère | ⏳ |

---

## Où j'en suis (étape 3)

Fichiers : `app/connection_manager.py`, `app/routers/live_chat.py`.

### Reste à faire dans `disconnect`
- [ ] Ne pas confondre `room` (le **set** d'un salon) et `self.rooms` (le **dict** de tous les salons)
- [ ] Tester si le **set** est vide, puis supprimer la **clé** dans le **dict**
- [ ] Éviter le `KeyError` quand le salon n'existe pas (cf. le test `not in` de `connect`)

### Reste à faire dans la route
- [ ] Importer `WebSocketDisconnect` depuis `fastapi`
- [ ] `try` / `except WebSocketDisconnect` : décider s'il entoure **toute la boucle** ou une seule ligne
- [ ] Appeler `disconnect` dans le `except` (`await` ou pas ? elle n'est pas `async`)

### Vérification
1. `print(self.rooms)` temporaire à la fin de `disconnect`
2. alice + bob sur le live 1, carol sur le live 2
3. Fermer bob → pas de trace d'erreur, bob disparaît de l'annuaire
4. alice écrit → elle reçoit toujours son message
5. Tout fermer → l'annuaire vaut `{}`

### Petits nettoyages en attente
- [ ] `broadcast` envoie `f'{ws} : {message}'` → envoyer juste `message` (préfixe `username` côté route si besoin)
- [ ] Retirer les `print(self.rooms)` une fois les tests faits
- [ ] Style : `class ConnectionManager:` (sans `()`), `self.rooms: dict` (sans espace avant `:`), instance en `snake_case` (`manager`)
- [ ] `main.py` : deux lignes vides avant `def root()`
- [ ] Fins de ligne CRLF/LF : vérifier `git diff --ignore-cr-at-eol --stat` avant de commit

---

## Notions acquises

- **Cycle de vie WebSocket** : demande HTTP `Upgrade` du client → `accept()` du serveur → boucle de messages → fermeture (`WebSocketDisconnect` côté serveur quand le client part)
- **Un seul manager** pour tous les lives, créé au niveau du module ; c'est un annuaire en mémoire, pas un serveur
- **Annuaire** : `dict[int, set[WebSocket]]` (`stream_id` → connexions)
- **Lire vs écrire une clé** : `d[k].methode()` lit (`KeyError` si absente) ; `d[k] = v` écrit
- **Deux boucles** : `while True` dans la route (dans le temps, on **reçoit**) ; `for` dans `broadcast` (sur les membres, on **envoie**)
- **Seule la route appelle `receive_text()`**
- **`async` sans `await`** : la coroutine n'est jamais exécutée
- Itérer sur `list(un_set)` pour éviter `Set changed size during iteration`

---

## Tester

- Serveur : `make live-chat` (depuis la racine, port **8002**)
- Client : `uvx websockets "ws://localhost:8002/streams/1/chat?user_id=1&username=alice"` (guillemets obligatoires à cause du `&`)
- Vérif rapide d'import : `uv run python -c "import app.main"` (depuis `live-chat/`)
- Tests auto : `cd live-chat && uv run pytest`
  - `client.websocket_connect(...)` dans un `with` ; imbriquer les `with` pour plusieurs clients
  - Piège : `receive_text()` bloque → pour tester une **absence** de message, faire envoyer un message par l'autre client et vérifier le premier reçu

---

## Pour l'oral

- **Limite** : le `ConnectionManager` vit en mémoire d'**un** processus → une seule instance de `live-chat`. Avec deux instances, alice (instance A) et bob (instance B) ne se verraient pas. Piste : Redis pub/sub (déjà dans le docker-compose).
- Pourquoi `receive_text()` plutôt que `receive_json()` : pouvoir répondre une erreur sur JSON invalide sans fermer la connexion.
- Pourquoi un `set` : pas de doublons, ajout/retrait en O(1), l'ordre n'a pas d'importance.
