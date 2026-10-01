# stream

Convertit le flux vidéo d'un streamer en HLS. `main` relaie les morceaux WebM envoyés par le navigateur du streamer, `stream` les passe à un ffmpeg (un par live) qui écrit une playlist HLS et ses segments sur disque. Le service n'est jamais exposé au front : tout passe par `main`.

```
navigateur ──WebM──> main ──WebSocket──> stream ──stdin──> ffmpeg ──> lives/{stream_id}/
                                                                       ├── index.m3u8
                                                                       └── index0.ts, index1.ts, ...
```

## Lancer

Depuis la racine du repo :

    make stream

ou depuis `stream/` :

    uv run fastapi dev --port 8001

`ffmpeg` doit être installé et dans le `PATH`.

| Variable    | Défaut  | Rôle                                                          |
|-------------|---------|---------------------------------------------------------------|
| `LIVES_DIR` | `lives` | Dossier de sortie HLS, relatif à `stream/`. Ignoré par Git.   |

Les variables se mettent dans `stream/.env` (copier `.env.example`).

## Endpoints

| Chemin                          | Protocole | Rôle                                  |
|---------------------------------|-----------|---------------------------------------|
| `/health`                       | HTTP GET  | Renvoie `{"status": "ok"}`            |
| `/streams/{stream_id}/ingest`   | WebSocket | Reçoit le flux WebM d'un live         |

### `/streams/{stream_id}/ingest`

Chaque message binaire reçu est écrit tel quel dans l'entrée de ffmpeg. Le premier morceau doit contenir l'en-tête WebM (c'est le cas du premier morceau produit par `MediaRecorder`).

Pour terminer un live, le client ferme simplement la connexion : ffmpeg termine la playlist et le live est fini.

Codes de fermeture envoyés par `stream` (à gérer côté `main`) :

| Code   | Quand                                                                   |
|--------|-------------------------------------------------------------------------|
| `1008` | Un ingest est déjà en cours pour ce `stream_id` (raison `Stream already live`) ou ce `stream_id` a déjà servi (raison `Stream id already used`) |
| `1011` | ffmpeg a planté (flux invalide, etc.). Le détail est dans les logs      |
| `1012` | `stream` s'arrête ou redémarre. La playlist est quand même terminée     |

Quand c'est le client qui ferme (fin normale du live, en général `1000`), `stream` n'envoie rien.

### Reconnexion

Un `stream_id` ne sert qu'une seule fois. Dès qu'un live a démarré, son dossier `lives/{stream_id}/` existe et toute nouvelle connexion sur ce `stream_id` est refusée (`1008`), même après la fin du live ou un redémarrage de `stream`. Les fichiers d'un live ne sont donc jamais écrasés : ils servent au replay.

Si le streamer est coupé, `main` doit créer une nouvelle session de live (donc un nouveau `stream_id`, voir #37). Le live coupé devient son propre replay.

## Sortie

Chaque live écrit dans `lives/{stream_id}/` : `index.m3u8` et des segments `.ts` de 4 s. La playlist est de type `EVENT` : les segments ne sont jamais supprimés, ce qui permet de la réutiliser pour le replay.

Pendant le live, la playlist grossit à chaque segment :

```
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:4
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:EVENT
#EXTINF:4.000000,
index0.ts
#EXTINF:4.000000,
index1.ts
```

À la fin du live (déconnexion du streamer ou arrêt du service), ffmpeg ajoute `#EXT-X-ENDLIST` en dernière ligne. Un lecteur qui voit cette ligne sait que le live est terminé. Si ffmpeg plante, cette ligne peut manquer.

## Tester

### Tests automatiques

    cd stream
    uv run pytest

Ce sont des tests unitaires : ffmpeg est remplacé par un faux processus, ils ne lancent rien et n'ont pas besoin de ffmpeg. Ils vérifient ce que le service envoie à ffmpeg et comment il ferme les connexions. La vraie conversion se teste à la main (ci-dessous).

### À la main

Dans un premier terminal, depuis `stream/` :

    uv run fastapi dev --port 8001

Dans un second terminal, depuis `stream/` :

    # générer une vidéo de test de 20 s (mire + bip)
    ffmpeg -f lavfi -i testsrc=duration=20:size=640x360:rate=25 -f lavfi -i sine=frequency=440:duration=20 -c:v libvpx -deadline realtime -c:a libopus sample.webm

    # l'envoyer comme le ferait un streamer, sur le live 42
    uv run python scripts/fake_streamer.py sample.webm 42

    # la playlist doit finir par #EXT-X-ENDLIST
    cat lives/42/index.m3u8

    # la regarder
    ffplay lives/42/index.m3u8

`uv run python scripts/fake_streamer.py --help` liste les options (`--url`, `--delay`).

## Limites

- L'état est en mémoire : si `stream` redémarre, les lives en cours s'arrêtent (leur playlist est terminée proprement, mais le streamer doit se reconnecter).
- Un processus ffmpeg par live : le nombre de lives simultanés est limité par le CPU de la machine.
- Latence de 15 à 20 s entre le streamer et les viewers, normale pour du HLS avec des segments de 4 s.
