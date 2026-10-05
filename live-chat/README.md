# live-chat

## Configuration

    cp .env.example .env

`DATABASE_URL` est obligatoire (le service refuse de démarrer sans). Les messages sont stockés dans la table `chat_messages` du schéma Postgres `live_chat` de la base `microservices`, créés automatiquement au démarrage (`docker compose up -d postgres` pour lancer Postgres).

## Run
    
    uv run fastapi dev --port 8002
    or
    make live-chat

## Test

    uv run pytest

## Utilisation du Micro-Service
Lorsqu'un "stream" est lancé avec le make live-chat, connectez un client en utilisant :
    
    uvx websockets "ws://localhost:8002/streams/1/chat?user_id=1&username=whateverusernameyouwant"

Les QueryParams sont optionnelles, mais si aucun user_id n'est renseigné, le chat sera uniquement en read only.

## Envoyer un message
Pour envoyer un message, un simple texte ne suffit pas. Le texte est parse depuis un json pour un envoi plus pratique.
Pour renseigner un message, envoyez dans le chat un élément comme ceci :
    
    {"content": "votremessageici"}

Le chat récupèrera le content et le renverra par la suite.

## Persistance
Chaque message est enregistré **avant** d'être diffusé. Si la base est indisponible, rien n'est diffusé et seul l'auteur reçoit :

    {"type": "error", "code": "MESSAGE_NOT_SAVED", "detail": "Le message n'a pas pu être enregistré"}

Le WebSocket reste ouvert et le service continue de tourner (il démarre aussi sans base ; le schéma est alors créé au premier message enregistré).

## Derniers messages
Un viewer qui arrive sur un live récupère les derniers messages, du plus ancien au plus récent :

    curl "http://localhost:8002/streams/1/messages?limit=50"

`limit` vaut 50 par défaut et doit être entre 1 et 100 (sinon `422`). Un live sans message renvoie `[]`. live-chat ne vérifie pas que le live existe : c'est `main` qui s'en charge. Si la base est indisponible, la route renvoie `503`.

## Cache
Les 100 derniers messages de chaque live sont gardés dans Redis, dans la liste `live-chat:stream:{id}:last` (`docker compose up -d redis` pour lancer Redis) :

- L'historique lit Redis d'abord ; si la clé est absente, il lit la base et remplit le cache
- Chaque nouveau message enregistré est ajouté au cache, s'il existe
- La clé expire après `CACHE_TTL_SECONDS` (60 secondes donc) : un message enregistré pendant le remplissage du cache revient au remplissage suivant
- Le remplissage n'écrit que si la clé est toujours absente (liste écrite à part puis `RENAMENX`) : quand plusieurs viewers ratent le cache en même temps, un remplissage plus ancien n'écrase pas un cache déjà rempli qui a reçu de nouveaux messages
- Si Redis est indisponible, l'historique est lu en base et le chat continue de fonctionner normalement
