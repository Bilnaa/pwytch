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

`ffmpeg` doit être installé et dans le `PATH`. Pour que les events partent, le broker MQTT doit tourner (`docker compose up -d mqtt` depuis la racine) ; sans lui le service démarre et les lives fonctionnent quand même.

| Variable    | Défaut  | Rôle                                                          |
|-------------|---------|---------------------------------------------------------------|
| `LIVES_DIR` | `lives` | Dossier de sortie HLS, relatif à `stream/`. Ignoré par Git.   |
| `RECONNECT_SECONDS` | `30` | Temps laissé au streamer pour revenir après une coupure      |
| `SIGNAL_TIMEOUT_SECONDS` | `10` | Sans aucune donnée pendant ce temps, le streamer est considéré comme coupé |
| `VIDEO_CRF` | `23` | Qualité x264 de la sortie HLS : plus bas, l'image est plus nette et les segments plus lourds (`18` est proche de la source) |
| `VIDEO_HEIGHT` | `720` | Hauteur maximale de la sortie HLS, en 16:9. Un flux plus grand est réduit, un flux plus petit n'est pas agrandi (`1080` laisse passer du 1920x1080, plus lourd pour le CPU et le disque) |
| `MQTT_HOST` | `localhost` | Hôte du broker MQTT (`mqtt` dans le docker-compose) |
| `MQTT_PORT` | `1883` | Port du broker MQTT |

Les variables se mettent dans `stream/.env` (copier `.env.example`).

En image Docker, le build se lance depuis la racine du repo, car l'image embarque `common` :

    docker build -f stream/Dockerfile -t stream .

## Endpoints

| Chemin                          | Protocole | Rôle                                  |
|---------------------------------|-----------|---------------------------------------|
| `/health`                       | HTTP GET  | `ok` ou `degraded` (ffmpeg et broker) |
| `/streams`                      | HTTP GET  | Liste les lives en cours              |
| `/streams/{stream_id}/ingest`   | WebSocket | Reçoit le flux WebM d'un live         |
| `/streams/{stream_id}/ingest`   | HTTP POST | Pareil en HTTP, pour tester sans webcam |
| `/lives/{stream_id}/{filename}` | HTTP GET  | Sert la playlist et les segments HLS  |

### `GET /health`

Renvoie `{"status": "ok"}` si `ffmpeg` est trouvé dans le `PATH` et que le client MQTT est connecté, `{"status": "degraded"}` sinon : sans ffmpeg aucun live ne peut être diffusé, sans broker les lives tournent mais les events sont perdus.

La réponse est toujours un `200` : le service répond, `status` dit s'il peut tout faire.

### `/streams/{stream_id}/ingest`

`main` ouvre la WebSocket avec les infos du live en query params, tous obligatoires :

| Param           | Type | Rôle                    |
|-----------------|------|-------------------------|
| `streamer_id`   | int  | Id du streamer          |
| `streamer_name` | str  | Nom affiché du streamer |
| `title`         | str  | Titre du live           |
| `game`          | str  | Jeu                     |

Exemple : `/streams/42/ingest?streamer_id=1&streamer_name=alice&title=Speedrun&game=Celeste`. `stream` les garde en mémoire sur le live. Ce sont ceux de la première connexion qui comptent : une reconnexion pendant `RECONNECT_SECONDS` doit les renvoyer, mais ne les change pas.

Chaque message binaire reçu est écrit tel quel dans l'entrée de ffmpeg. Le premier morceau doit contenir l'en-tête WebM (c'est le cas du premier morceau produit par `MediaRecorder`).

Quand le client ferme la connexion, le live n'est pas fini tout de suite : les viewers voient l'écran « Signal lost » pendant `RECONNECT_SECONDS`, puis le live se termine (voir « Coupure et reconnexion »).

Codes de fermeture envoyés par `stream` (à gérer côté `main`) :

| Code   | Quand                                                                   |
|--------|-------------------------------------------------------------------------|
| `1008` | Un ingest est déjà en cours pour ce `stream_id` (raison `Stream already live`), ce `stream_id` a déjà servi (raison `Stream id already used`) ou il manque un query param (sans raison) |
| `1011` | ffmpeg a planté (flux invalide, etc.). Le détail est dans les logs      |
| `1012` | `stream` s'arrête ou redémarre. La playlist est quand même terminée     |
| `1013` | Aucune donnée reçue depuis `SIGNAL_TIMEOUT_SECONDS` (raison `No data received`). Traité comme une coupure : il faut se reconnecter sur le même `stream_id` |

Quand c'est le client qui ferme (fin normale du live, en général `1000`), `stream` n'envoie rien.

### `POST /streams/{stream_id}/ingest`

Outil de dev : permet de simuler un streamer sans webcam, sans front et sans `main`. `main` ne l'expose jamais.

Le corps de la requête est lu au fur et à mesure et envoyé au même ffmpeg que la WebSocket : même sortie HLS, même écran « Signal lost » à la fin, mêmes refus. ffmpeg détecte le format tout seul, on peut donc envoyer du MPEG-TS comme du WebM (voir « À la main »).

Les query params sont les mêmes que ceux de la WebSocket, mais facultatifs : `streamer_id=0`, `streamer_name=dev`, `title=Dev live` et `game=Dev` par défaut.

| Code  | Quand                                                              |
|-------|--------------------------------------------------------------------|
| `204` | Tout le corps a été envoyé à ffmpeg                                |
| `409` | Même cas que le `1008` de la WebSocket (`Stream already live` ou `Stream id already used`) |
| `500` | ffmpeg a planté pendant l'envoi. Le détail est dans les logs       |

Un fichier que ffmpeg ne sait pas lire renvoie quand même `204` : ffmpeg attend la fin du corps pour abandonner, l'erreur n'apparaît que dans les logs. Si la playlist ne contient que l'écran « Signal lost », c'est ça.

### Coupure et reconnexion

Comme sur Twitch, une coupure du streamer ne termine pas le live :

1. Le streamer se déconnecte (fin du live ou coupure réseau), ou n'envoie plus rien pendant `SIGNAL_TIMEOUT_SECONDS` (streamer figé, `main` bloqué ou tombé sans fermer la connexion) : ffmpeg termine son segment, puis un second ffmpeg prend le relais et diffuse en boucle la vidéo « Signal lost » (`assets/slate.mp4`) dans la même playlist.
2. Si le streamer se reconnecte sur le même `stream_id` avant `RECONNECT_SECONDS`, l'écran s'arrête et le live reprend, toujours dans la même playlist.
3. Sinon, le live se termine : la playlist reçoit `#EXT-X-ENDLIST` et devient le replay.

La vidéo est une boucle de 6 s en 1280x720, mise à la taille du live. Pour la changer, il suffit de remplacer `assets/slate.mp4` (elle est lue en boucle, sa durée n'a pas d'importance).

Chaque passage live / écran est séparé par un `#EXT-X-DISCONTINUITY` dans la playlist, ce qui permet au lecteur (hls.js) d'enchaîner sans couper. La taille du live est choisie à la première connexion : le cadre 16:9 qui contient le flux du streamer, sans dépasser `VIDEO_HEIGHT` (une webcam 720p reste en 720p, une source 4K est réduite). L'écran « Signal lost » et les reconnexions reprennent ensuite cette taille, relue avec `ffprobe` dans le premier segment (`index0.ts`). Tout un live est donc encodé à la même taille et à 30 i/s, pour que le replay s'exporte toujours avec `-c copy`.

Un `stream_id` terminé ne sert plus jamais : toute connexion dessus est refusée (`1008`, raison `Stream id already used`), même après un redémarrage de `stream`, puisque son dossier `lives/{stream_id}/` existe. Les fichiers d'un live ne sont donc jamais écrasés.

Pour `main` : un « Go live » après la fin d'un live doit créer une nouvelle session (nouveau `stream_id`, voir #37). Pendant les `RECONNECT_SECONDS` qui suivent une coupure, il faut au contraire se reconnecter sur le même `stream_id`.

### `/lives/{stream_id}/{filename}`

Le dossier `lives/` est monté en statique (`StaticFiles`) : `GET /lives/42/index.m3u8` renvoie la playlist, `GET /lives/42/index0.ts` un segment, 404 si le fichier n'existe pas. Appelé par `main` (relais vers les viewers) et `replay` (export mp4), jamais par le front.

Les fichiers d'un live terminé restent servis, c'est ce qu'utilise le replay. On ne peut pas sortir du dossier (`/lives/../.env` renvoie 404) et il n'y a pas de listing des dossiers.

## Events MQTT

`stream` publie le début et la fin de chaque live avec le `MqttClient` de `common` (`app/events.py`), en QoS 1. Les modèles sont dans `common.events`.

| Topic            | Modèle          | Quand                                                              |
|------------------|-----------------|--------------------------------------------------------------------|
| `stream/started` | `StreamStarted` | Le premier ffmpeg du live a démarré. Une reconnexion ne le republie pas |
| `stream/ended`   | `StreamEnded`   | La playlist a reçu `#EXT-X-ENDLIST` : délai de reconnexion écoulé, arrêt du service, ou au démarrage suivant si le service a été coupé net |

```json
{"event_id": "4070bf93-...", "version": 1, "stream_id": 42, "streamer_id": 1, "streamer_name": "alice", "title": "Speedrun", "game": "Celeste", "started_at": "2026-10-02T12:23:22.099239Z"}
{"event_id": "268c466d-...", "version": 1, "stream_id": 42, "streamer_id": 1, "ended_at": "2026-10-02T12:53:29.962198Z", "duration_s": 1807.86, "reason": "normal"}
```

- `streamer_id`, `streamer_name`, `title` et `game` sont ceux reçus à la première connexion de l'ingest
- `duration_s` va de `started_at` à `ended_at` : il compte les écrans « Signal lost », y compris le dernier (`RECONNECT_SECONDS`)
- `reason` vaut `error` si le dernier ffmpeg du streamer a planté (code de sortie différent de 0), `normal` sinon. Un plantage ne termine pas le live plus vite : l'event part après le délai de reconnexion, comme pour une coupure. Si le streamer revient entre-temps et finit normalement, c'est `normal`
- Un live dont le premier ffmpeg n'a jamais démarré ne publie rien

La connexion au broker se fait en tâche de fond au démarrage et se rétablit toute seule. Si le broker est injoignable au moment de publier, l'erreur est journalisée (`Event stream/started not published`) et le live continue. L'event est alors perdu : il n'est pas renvoyé plus tard.

## Redémarrage

Un arrêt normal (`SIGTERM`, `docker compose stop`) termine les lives en cours avant de quitter. Si le service est coupé net (plantage, `kill -9`, machine éteinte), il n'a le temps de rien faire : les playlists restent sans `#EXT-X-ENDLIST` et personne ne reçoit `stream/ended`.

Au démarrage, `stream` parcourt donc `LIVES_DIR` (`app/recovery.py`). Pour chaque playlist sans `#EXT-X-ENDLIST` :

- il ajoute `#EXT-X-ENDLIST` : le live devient un replay, avec ce qui a été écrit avant la coupure
- il publie `stream/ended` avec `reason: "error"`, dès que le broker est connecté (il l'attend 30 s au plus, ensuite l'event est perdu comme les autres)

L'état en mémoire étant perdu, le `streamer_id` et l'heure de début sont relus dans `lives/{stream_id}/started.json`, une copie de l'event `stream/started` écrite au début du live. `ended_at` est la date de dernière modification de la playlist (le dernier segment écrit par ffmpeg), pas l'heure du redémarrage, et `duration_s` est calculé à partir de là.

Une playlist sans `started.json` lisible (live créé avant cette fonctionnalité, fichier coupé pendant son écriture) est terminée aussi, mais sans event : un avertissement est journalisé. Si `started.json` ne peut pas être écrit au début d'un live, une erreur est journalisée et le live continue.

Le live ne reprend pas : son `stream_id` est terminé, le streamer doit en relancer un nouveau.

## Sortie

Chaque live écrit dans `lives/{stream_id}/` : `index.m3u8`, des segments `.ts` de 4 s et `started.json` (voir « Redémarrage »). La playlist est de type `EVENT` : les segments ne sont jamais supprimés, ce qui permet de la réutiliser pour le replay.

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

À la fin du live (délai de reconnexion écoulé, arrêt du service, ou démarrage suivant après une coupure nette), `stream` ajoute `#EXT-X-ENDLIST` en dernière ligne. Un lecteur qui voit cette ligne sait que le live est terminé.

## Tester

### Tests automatiques

    cd stream
    uv run pytest

Ce sont des tests unitaires : ffmpeg est remplacé par un faux processus et le client MQTT par un faux client, ils ne lancent rien et n'ont besoin ni de ffmpeg ni d'un broker. Ils vérifient ce que le service envoie à ffmpeg et comment il ferme les connexions. La vraie conversion se teste à la main (ci-dessous).

### À la main

Dans un premier terminal, depuis `stream/` :

    uv run fastapi dev --port 8001

Dans un second terminal, depuis `stream/` :

    # générer une vidéo de test de 20 s (mire + bip)
    ffmpeg -f lavfi -i testsrc=duration=20:size=640x360:rate=25 -f lavfi -i sine=frequency=440:duration=20 -c:v libvpx -deadline realtime -c:a libopus sample.webm

    # l'envoyer comme le ferait un streamer, sur le live 42
    uv run python scripts/fake_streamer.py sample.webm 42

    # pendant 30 s la playlist reçoit l'écran « Signal lost », puis finit par #EXT-X-ENDLIST
    cat lives/42/index.m3u8

    # la regarder
    ffplay lives/42/index.m3u8

    # ou la récupérer en HTTP, comme le fera main
    curl -i http://localhost:8001/lives/42/index.m3u8
    ffplay http://localhost:8001/lives/42/index.m3u8

Pendant l'envoi et l'écran « Signal lost », `curl http://localhost:8001/streams` renvoie `[42]`, puis `[]` une fois le live terminé.

`uv run python scripts/fake_streamer.py --help` liste les options (`--url`, `--delay`). Le script envoie des infos de live fixes (`streamer_id=1`, `streamer_name=fake`, ...) ; pour en envoyer d'autres, passer l'URL complète avec `--url`.

Sans le script, en HTTP (`-re` envoie la vidéo à sa vitesse réelle, comme un vrai live) :

    # une mire de 20 s, sans fichier
    ffmpeg -re -f lavfi -i testsrc=duration=20:size=640x360:rate=25 -f lavfi -i sine=frequency=440:duration=20 -c:v libx264 -c:a aac -f mpegts http://localhost:8001/streams/43/ingest

    # ou une vraie vidéo
    ffmpeg -re -i video.mp4 -c:v libx264 -c:a aac -f mpegts http://localhost:8001/streams/44/ingest

Pour voir les events : lancer le broker, écouter les topics dans un troisième terminal, puis envoyer une vidéo. `stream/started` arrive tout de suite, `stream/ended` après `RECONNECT_SECONDS`.

    docker compose up -d mqtt
    docker compose exec mqtt mosquitto_sub -t 'stream/#' -v

Avec `docker compose stop mqtt`, le live se déroule pareil et les logs de `stream` affichent `Event stream/started not published`.

Pour voir une connexion qui reste ouverte sans rien envoyer : lancer le service avec `SIGNAL_TIMEOUT_SECONDS=5` et envoyer la vidéo avec `--delay 8`. Le script affiche `connection closed by the server (1013)` et la playlist passe sur l'écran « Signal lost ».

Pour voir une coupure puis une reprise : lancer le service avec `RECONNECT_SECONDS=15`, envoyer la vidéo, attendre quelques secondes et la renvoyer sur le même live. La playlist contient alors live, écran, live, écran, puis `#EXT-X-ENDLIST`.

Pour voir un live coupé par un redémarrage : lancer le service avec `fastapi run` (sans le rechargement automatique de `fastapi dev`, qui garde un second processus), envoyer une vidéo, tuer le service pendant l'envoi, puis le relancer. La playlist finit par `#EXT-X-ENDLIST` et `mosquitto_sub` affiche `stream/ended` avec `"reason":"error"`.

    uv run fastapi run --port 8001
    # pendant l'envoi de la vidéo (Ctrl+C ne suffit pas, il arrête le service proprement)
    pkill -9 -f "fastapi run --port 8001"
    uv run fastapi run --port 8001
    tail -1 lives/42/index.m3u8

## Chaînes musicales

`scripts/channels.py` fait tourner des chaînes en continu (lo-fi, K-pop, ...) pour la démo. Chaque sous-dossier de `channels/` est une chaîne : le script lui crée un compte sur `main` (`lofi_radio` pour le dossier `lofi`), ouvre une session de live et envoie ses morceaux en boucle, dans un ordre aléatoire, sur l'ingest WebSocket de `main`. Pour `main` et `stream`, c'est un streamer comme un autre : la chaîne apparaît dans `GET /streams?status=live` et publie les mêmes events.

```
channels/
├── lofi/
│   ├── cover.jpg
│   ├── track1.mp3
│   └── track2.mp3
└── kpop/
    ├── clip1.mp4
    └── clip2.mp4
```

- un fichier vidéo (`.mp4`, `.mkv`, `.mov`, `.webm`) est diffusé tel quel : c'est le clip du morceau
- un fichier audio (`.mp3`, `.m4a`, `.flac`, `.wav`, `.ogg`, `.opus`) n'est jamais diffusé tel quel : le script en fait d'abord une vidéo qui prend sa place (`track1.mp3` devient `track1.mp4`, le fichier audio est supprimé une fois la vidéo entière). On y voit le spectre du morceau en anneau autour de la pochette, avec la pochette floutée en fond

Seules les vidéos sont diffusées. Fabriquer celle d'un morceau prend à peu près un tiers de sa durée, en tâche de fond et en basse priorité (`nice`) : le morceau entre dans la rotation quand sa vidéo est prête, et une chaîne qui n'a que des fichiers audio démarre à la première. Garder une copie des fichiers audio ailleurs : la suppression est définitive. Un fichier audio qui a déjà une vidéo du même nom n'est ni refait ni supprimé.

La pochette est, dans l'ordre : l'image contenue dans le fichier (tag ID3 d'un mp3 ou d'un wav, m4a, flac), une image du même nom que le morceau (`track1.jpg`), `cover.*`. Seul son centre carré est utilisé. Sans pochette, l'anneau est seul sur un fond uni.

`channels/` est ignoré par Git : chacun y met ses propres fichiers.

Le nom d'un dossier fait 24 caractères au plus (il sert de nom de compte sur `main`, avec `_radio` à la fin) : un dossier au nom plus long est ignoré.

Le dossier d'une chaîne est relu à chaque passage : un fichier ajouté pendant que le script tourne est pris en compte sans rien relancer (y déposer un fichier complet, pas un téléchargement en cours). Un passage ne commence jamais par le morceau qui a fini le précédent.

`main` et `stream` doivent tourner (avec postgres et le broker). Depuis `stream/` :

    uv run python scripts/channels.py

Le script envoie du 1080p. Pour que les viewers le reçoivent tel quel, lancer `stream` avec `VIDEO_HEIGHT=1080` (et `VIDEO_CRF=18` pour une image plus nette) ; sinon il est réduit en 720p. Le script agrandit lui-même les fichiers plus petits : tous les morceaux d'une chaîne doivent sortir à la même taille.

Le script affiche l'URL de la playlist de chaque chaîne et le morceau en cours. `--help` liste les options (`--api`, `--password`, un autre dossier que `channels/`). `--api` est l'URL de l'API de `main`, `http://localhost:8000/api` par défaut.

`Ctrl+C` arrête les chaînes : les viewers voient l'écran « Signal lost », puis les lives se terminent. Relancé avant `RECONNECT_SECONDS`, le script reprend les mêmes lives ; après, il en crée de nouveaux. Si `main` ou `stream` tombe, il réessaie toutes les 5 s.

## Limites

- L'état est en mémoire : si `stream` redémarre, les lives en cours (et ceux sur l'écran « Signal lost ») s'arrêtent. Leur playlist est terminée, à l'arrêt ou au démarrage suivant, mais le streamer doit relancer un live avec un nouveau `stream_id`.
- Hors Docker, un `kill -9` pendant l'écran « Signal lost » laisse son ffmpeg tourner tout seul : il continue d'écrire dans la playlist et efface le `#EXT-X-ENDLIST` ajouté au redémarrage. Il faut le tuer à la main (`pkill -f stream_loop`) puis relancer le service. Dans un conteneur le problème n'existe pas, ffmpeg meurt avec lui.
- Au redémarrage, `#EXT-X-ENDLIST` est écrit avant que `stream/ended` soit publié, et c'est lui qui marque le live comme traité. Si le broker met plus de 30 s à revenir, ou si le service est arrêté pendant l'attente, l'event n'est pas renvoyé au démarrage suivant.
- Une seule instance de `stream` par dossier `LIVES_DIR` : une seconde instance (ou `--workers 2`) terminerait au démarrage les lives encore en cours de l'autre.
- Un live coupé net avant son premier segment (moins de 4 s) n'a pas de playlist : il n'est pas détecté au redémarrage et son `stream/ended` ne part jamais.
- Un event qui n'a pas pu être publié (broker injoignable) est perdu : `main` ne saura pas que le live a commencé ou fini.
- Un processus ffmpeg par live : le nombre de lives simultanés est limité par le CPU de la machine.
- Latence de 15 à 20 s entre le streamer et les viewers, normale pour du HLS avec des segments de 4 s.
- Une chaîne musicale est un live qui ne finit pas : sa playlist et ses segments grossissent tant qu'elle tourne (environ 1 Go par heure et par chaîne en 720p, plus de 2 Go en 1080p), et chaque chaîne occupe deux ffmpeg (celui du script, celui de `stream`).
- Si `main` rate le `stream/ended` d'une chaîne (broker coupé), sa session reste `live` alors que `stream` l'a terminée : le script affiche `Stream id already used` en boucle, jusqu'à ce que la session soit passée en `ended` côté `main` (#107).
- Un live coupé avant son premier segment (moins de 4 s) n'a pas de taille connue : son écran « Signal lost » sort en 1280x720, et une reconnexion choisit sa taille à nouveau.
