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

`/{username}`, comme sur Twitch (`/aespa_radio`) : player HLS (`components/hls-player.tsx`) sur `/api/lives/{id}/index.m3u8`, avec le streamer, le titre, le jeu et le badge LIVE. Pas besoin d'être connecté. Les chemins fixes (`/login`, `/go-live`...) passent avant : un compte nommé `login` n'aurait pas de page.

`main` ne filtre pas `/streams` par streamer : la page cherche le nom dans `GET /streams?status=live&size=100` (`findLive()` dans `lib/streams.ts`). Pas en live, ou nom inconnu : « {username} is offline ».

hls.js (build `light`) n'est chargé qu'à l'ouverture d'une chaîne (`lazy` dans `main.tsx`), Safari lit le HLS sans lui. Tant que la playlist n'existe pas (début du live), le player réessaie toutes les 3 s.

Pour avoir un live à regarder sans webcam : `uv run python scripts/channels.py` depuis `stream/` (voir `stream/README.md`).

## Pages et routes de l'API

Comme l'API est sous `/api`, une page peut avoir le même chemin qu'une route de l'API (`/search` côté front, `/api/search` côté API). Recharger une page renvoie toujours le front.
