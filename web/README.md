# web

Front de Pwytch. Il n'appelle que `main`, sous `/api`.

## Techno

- [React](https://react.dev/) + TypeScript, buildé avec [Vite](https://vite.dev/)
- [React Router](https://reactrouter.com/) en mode « data » (`createBrowserRouter`)
- [Tailwind CSS](https://tailwindcss.com/) v4, via le plugin Vite
- [shadcn/ui](https://ui.shadcn.com/) pour les composants (`src/components/ui`)

Le build (`dist/`) est servi par `main` avec `app.frontend()` de FastAPI : pas de serveur à part en prod, et le front et l'API sont sur la même origine. L'image Docker de `main` build le front elle-même (voir `main/Dockerfile`).

## Lancer

Prérequis : Node.js 22 ou plus. Depuis la racine du repo :

    make web          # dev sur http://localhost:5173, avec rechargement à chaud
    make web-build    # build dans web/dist, servi par main sur http://localhost:8000

`main` doit tourner (`make main`) pour que les appels à l'API marchent. Après un `make web-build`, redémarrer `main` s'il tournait sans `web/dist` : il ne regarde le dossier qu'au démarrage.

| Variable       | Défaut | Rôle |
|----------------|--------|------|
| `VITE_API_URL` | vide   | URL de `main`, sans `/api` ni `/` final. Vide = même origine, le cas du build servi par `main`. `.env.development` la met à `http://localhost:8000` pour `npm run dev` |

Elle est lue au build : la changer demande de relancer `npm run dev` ou de rebuilder.

## Organisation

| Chemin                   | Rôle |
|--------------------------|------|
| `src/main.tsx`           | Routes de l'app |
| `src/components/layout.tsx` | Layout commun avec le header, les pages s'affichent dans son `<Outlet />` |
| `src/components/auth-form.tsx` | Carte de formulaire commune à `/login` et `/register`, les champs sont passés en enfants |
| `src/components/form-field.tsx` | Label + input + petite aide sous le champ |
| `src/components/ui/`     | Composants shadcn, ajoutés avec `npx shadcn@latest add <composant>` |
| `src/lib/api.ts`         | Client d'API |
| `src/lib/auth.tsx`       | `useAuth()` : utilisateur connecté, login, register, logout |
| `src/lib/theme.ts`       | Thème clair / sombre |
| `src/lib/streams.ts`     | Type `Stream` et appels à `/streams` |
| `src/lib/replays.ts`     | Type `Replay` et appels à `/replays` (liste, détail, demande du `.mp4`) |
| `src/hooks/`             | Hooks : webcam (`use-webcam`), envoi du flux à `main` (`use-broadcast`) |
| `src/components/require-auth.tsx` | Routes réservées aux utilisateurs connectés, renvoie vers `/login` sinon |
| `src/pages/`             | Une page par fichier |

## Client d'API

    import { api } from '@/lib/api'

    const me = await api<User>('/auth/me')
    const live = await api<Stream>('/streams', { method: 'POST', body: JSON.stringify({ title, game }) })

`api()` préfixe le chemin par `/api`, ajoute `Authorization: Bearer <jeton>` si un jeton est dans le `localStorage` (`setToken()` après le login) et met `Content-Type: application/json` quand le corps est une chaîne (`JSON.stringify`). Pour un formulaire, comme `/auth/login`, passer un `URLSearchParams` : `fetch` met le bon type tout seul. Sur un `401`, il efface le jeton et renvoie vers `/login`. Toute autre erreur lève une `ApiError` avec le `status` et le `detail` de FastAPI (une chaîne, ou la liste des erreurs sur un `422`).

## Thème

Bleu et jaune de Python (`#3776AB`, `#FFD43B`), fond sombre comme Twitch. Les couleurs sont dans `src/index.css`. Sombre par défaut, le bouton du header passe en clair (gardé dans le `localStorage`).

## Go live

`/go-live` : aperçu de la webcam, titre et jeu, puis « Go live » crée une session (`POST /streams`) et ouvre `wsUrl('/streams/{id}/ingest?token=')`. Le `MediaRecorder` ne démarre qu'une fois la WebSocket ouverte et envoie un morceau WebM par seconde. Les codes de fermeture de `main` sont traduits en message dans `use-broadcast.ts`.

Le navigateur doit savoir enregistrer du WebM (Chrome, Firefox). Pour tester sans webcam, lancer Chrome avec `--use-fake-device-for-media-stream`.

## Accueil

`/` : une carte par live en cours (`GET /streams?status=live`), rafraîchie toutes les 15 s. Un clic ouvre la chaîne (`/{username}`). Pas encore de miniature dans l'API : la carte a un dégradé bleu / jaune avec l'initiale du streamer.

## Page d'une chaîne

`/{username}`, comme sur Twitch (`/aespa_radio`) : player [Vidstack](https://vidstack.io) (`components/hls-player.tsx`) sur `/api/lives/{id}/index.m3u8`, avec le streamer, le titre, le jeu et le badge LIVE. Pas besoin d'être connecté. Les chemins fixes (`/login`, `/go-live`...) passent avant : un compte nommé `login` n'aurait pas de page.

`main` ne filtre pas `/streams` par streamer : la page cherche le nom dans `GET /streams?status=live&size=100` (`findLive()` dans `lib/streams.ts`). Pas en live, ou nom inconnu : « {username} is offline ».

Vidstack lit le HLS avec hls.js (build `light`, passé à Vidstack pour qu'il ne le télécharge pas depuis un CDN). Les deux ne sont chargés qu'à l'ouverture d'une chaîne (`lazy` dans `main.tsx`), Safari lit le HLS sans hls.js. Tant que la playlist n'existe pas (début du live), le player réessaie toutes les 3 s.

Chaque play, pause et stop du player part sur `POST /api/streams/{id}/player-events` pour les stats (`hooks/use-player-events.ts`). Stop = fin du live, ou on quitte la page pendant la lecture (lien, onglet fermé). L'envoi n'est jamais attendu et ses erreurs sont ignorées, la lecture ne dépend pas de `main`.

Pour avoir un live à regarder sans webcam : `uv run python scripts/channels.py` depuis `stream/` (voir `stream/README.md`).

## Replays

`/replays` : une carte par live terminé (`GET /replays?page=&size=24`), du plus récent au plus ancien, avec la durée, le titre, le streamer, le jeu et la date. Le numéro de page est dans l'URL (`/replays?page=2`) ; une page au-delà de la dernière propose de revenir à la première. Un champ manquant (replay reçu sans le début du live) s'affiche « Untitled » ou « Unknown streamer ».

`/replays/{id}` : le même player que les lives, en `streamType="on-demand"` : barre de progression sur tout le live, et pas de nouvel essai en boucle si la playlist manque. `playback_url` du replay est relatif à l'API de `main` et passe par `apiUrl()`. Replay inconnu, live encore en cours ou id invalide : page 404. Chargée à la demande (`lazy`), comme la page d'une chaîne.

Bouton « Download .mp4 » (`components/download-button.tsx`) : le `.mp4` n'est créé qu'à la première demande.

- Déjà prêt (`mp4_status: ready`) : lien direct vers `/api/replays/{id}/download`, le navigateur enregistre le fichier (`Content-Disposition: attachment`) sans le charger en mémoire.
- Sinon, un `fetch` de `/download` lance la conversion : sur le `202`, le bouton affiche « Preparing... » et relit le replay (`GET /replays/{id}`) toutes les `Retry-After` secondes, puis enregistre le fichier dès que le statut est `ready`.
- Conversion ratée : « Try again ». `replay` répond `500` une fois puis remet la conversion à zéro, le bouton redemande donc tout de suite pour la relancer.

Quitter la page arrête l'attente.

## Chat

À côté du player sur la page d'une chaîne (en dessous sur mobile), et sur `/go-live` pour le streamer pendant son live. `wsUrl('/streams/{id}/chat')`, avec `?token=` si on est connecté (`hooks/use-chat.ts`). Sans compte, le chat est en lecture seule avec un lien « Log in » qui ramène sur la chaîne.

Les erreurs de `live-chat` arrivent avec un `code` (`EMPTY_MESSAGE`, `CONTENT_TOO_LONG`...) traduit en message sous le champ. Si la connexion coupe (`main` redémarré, `live-chat` down), le chat se reconnecte toutes les 3 s, sauf sur 4401 (session expirée) et 4404 (live inconnu). Pas encore d'historique à l'arrivée ni des messages manqués pendant une coupure, en attendant la route de #84.

## Pages et routes de l'API

Comme l'API est sous `/api`, une page peut avoir le même chemin qu'une route de l'API (`/search` côté front, `/api/search` côté API). Recharger une page renvoie toujours le front.
