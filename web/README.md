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

## Chat

À côté du player sur la page d'une chaîne (en dessous sur mobile), et sur `/go-live` pour le streamer pendant son live. `wsUrl('/streams/{id}/chat')`, avec `?token=` si on est connecté (`hooks/use-chat.ts`). Sans compte, le chat est en lecture seule avec un lien « Log in » qui ramène sur la chaîne.

Les erreurs de `live-chat` arrivent avec un `code` (`EMPTY_MESSAGE`, `CONTENT_TOO_LONG`...) traduit en message sous le champ. Si la connexion coupe (`main` redémarré, `live-chat` down), le chat se reconnecte toutes les 3 s, sauf sur 4401 (session expirée) et 4404 (live inconnu). Pas encore d'historique à l'arrivée ni des messages manqués pendant une coupure, en attendant la route de #84.

## Recherche

Une barre dans le header, sur toutes les pages comme sur Twitch (`components/search-bar.tsx`). Entrée ouvre `/search?q=`, et une fois sur la page les résultats suivent la saisie 300 ms après la dernière touche. Moins de 2 caractères : pas d'appel (`main` répond 422).

Un seul appel, `GET /search?q=`, pour les deux sections : « Streamers » (badge LIVE s'il est en direct, lien vers sa chaîne) et « Messages ». Une section vide n'est pas affichée.

Un message ne connaît que l'id de son live : il pointe vers `/videos/{id}` (`pages/video.tsx`), qui fait `GET /streams/{id}` au clic et renvoie sur la chaîne du streamer. Id inconnu : page 404.

## Follows et bookmarks

Comme sur Twitch, un streamer se suit et un replay se met de côté. Les deux sont des bookmarks côté API : un follow est un bookmark de type `streamer`, avec le nom du streamer en libellé.

- Page d'une chaîne : bouton « Follow » / « Following » (`components/follow-button.tsx`), seulement si on est connecté et pas sur sa propre chaîne. Pour savoir si on suit déjà le streamer, il cherche son id dans `GET /bookmarks?target_type=streamer&size=100` (`bookmarks` ne filtre pas par `target_id`). Un deuxième clic supprime le bookmark. Un 409 (suivi depuis un autre onglet) recharge le follow existant.
- `/bookmarks`, réservée aux comptes connectés, avec deux onglets paginés par 20 (`?tab=replays&page=2` dans l'URL). « Following » : les streamers suivis, avec un lien vers leur chaîne et « Unfollow ». Les noms viennent de `GET /users?id=...`, un appel pour toute la page. « Replays » : libellé et note modifiables, suppression avec confirmation. La confirmation s'affiche sous le texte, pas à la place du bouton, pour qu'un double clic ne supprime rien.

Barre à gauche avec les chaînes suivies, comme sur Twitch (`components/followed-sidebar.tsx`), seulement si on est connecté et sur grand écran. Les chaînes en live d'abord (avec leur jeu), puis les autres par nom, grisées et marquées « Offline ». Trois appels : les follows, puis en même temps leurs noms (`GET /users?id=...`) et les lives en cours (`GET /streams?status=live`). Rafraîchie toutes les 15 s comme l'accueil, et tout de suite après un follow ou un unfollow (event `follows-changed` sur `window`).

Le bouton pour mettre un replay de côté arrive avec les pages replays (#131).

## Pages et routes de l'API

Comme l'API est sous `/api`, une page peut avoir le même chemin qu'une route de l'API (`/search` côté front, `/api/search` côté API). Recharger une page renvoie toujours le front.
