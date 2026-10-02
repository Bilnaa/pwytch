# live-chat

## Run

    make live-chat

## Test
Lorsqu'un "stream" est lancé avec le make live-chat, connectez un client en utilisant :
    
    uvx websockets "ws://localhost:8002/streams/1/chat?user_id=1&username=whateverusernameyouwant"

Les QueryParams sont optionnelles, mais si aucun user_id n'est renseigné, le chat sera uniquement en read only.

## Envoyer un message
Pour envoyer un message, un simple texte ne suffit pas. Le texte est parse depuis un json pour un envoi plus pratique.
Pour renseigner un message, envoyez dans le chat un élément comme ceci :
    
    {"content": "votremessageici"}

Le chat récupèrera le content et le renverra par la suite.

