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
