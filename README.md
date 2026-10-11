# LFINFO Network Controller

Console React pour administrer les quatre switches TP-Link Easy Smart LFINFO via FastAPI et `tplink-tool`. Les lectures affichées proviennent des switches : aucune donnée de démonstration n’est injectée.

## Architecture

- `app.py` : API FastAPI, authentification HTTP Basic et SDK.
- `src/` : React 19, TypeScript strict, React Router, TanStack Query, Tailwind, Radix UI et Recharts.
- `src/services/api.ts` : unique couche d’accès à `/api`.
- `static/react/` : build de production servi par FastAPI après compilation.

Les switches sont TL-SG108E (`10.0.60.200`), TL-SG108PE (`10.0.60.201`), TL-SG105PE (`10.0.60.252`) et TL-SG105E (`10.0.60.253`). Le backend conserve le forçage `model="Switch"` requis par le TL-SG105PE.

## Installation sur TLManager

```bash
cd /opt/lfinfo-switch-controller
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env # seulement lors d'une première installation
chmod 600 .env
nano .env

# Installer Node.js 20+ puis compiler l'interface
npm ci
npm run build
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8088
```

Ouvrir `http://adresse-du-serveur:8088`. En développement, lancer FastAPI puis `npm run dev`; Vite transmet `/api` vers `http://127.0.0.1:8088`.

## Mise à jour

```bash
cd /opt/lfinfo-switch-controller
git pull
.venv/bin/pip install -r requirements.txt
npm ci
npm run build
sudo systemctl restart tlmanager
```

Préservez toujours le fichier `.env` existant.

## Sécurité et limitations

- `ENABLE_WRITES=false` désactive les écritures par défaut.
- L’interface confirme explicitement les actions et signale le risque pour les uplinks, trunks et VLAN d’administration. Aucun chargement de page n’écrit sur le réseau.
- Les mots de passe restent dans `.env` côté serveur, jamais dans le navigateur ou `localStorage`.
- La modification des appartenances VLAN, les exports de sauvegarde, PoE, et les compteurs TX/RX/erreurs ne sont pas disponibles car l’API actuelle ne les expose pas de façon validée sur les quatre firmwares.
- Placez FastAPI derrière HTTPS ou un tunnel SSH et limitez l’accès au VLAN d’administration.
