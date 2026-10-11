# LFINFO Network Controller

Console React pour administrer les quatre switches TP-Link Easy Smart LFINFO via FastAPI et `tplink-tool`. Les lectures affichées proviennent des switches : aucune donnée de démonstration n’est injectée.

## Architecture

- `app.py` : API FastAPI, authentification HTTP Basic et SDK.
- `data/controller.db` : inventaire SQLite, journaux d’audit et instantanés de configuration (créé au démarrage, exclu de Git).
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

## Switches gérés par SQLite

Au premier démarrage, configurez une clé Fernet propre au contrôleur dans `.env` :

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copiez cette valeur dans `SWITCH_DB_ENCRYPTION_KEY`. Cette clé chiffre les identifiants avant leur écriture dans `data/controller.db`; elle ne doit jamais être perdue ni ajoutée au dépôt. `ADMIN_PASSWORD` reste le secret d’accès HTTP Basic.

Dans **Paramètres**, utilisez **Importer l’ancienne configuration** pour transférer les quatre équipements depuis les anciennes variables `SW_108E_PASSWORD`, `SW_108PE_PASSWORD`, `SW_105PE_PASSWORD` et `SW_105E_PASSWORD`. L’import évite les doublons. Une fois vérifié, retirez ces quatre variables du `.env`.

La même page permet d’ajouter, modifier, supprimer ou tester un switch sans redémarrer FastAPI. Lors de l’ajout, seuls l’adresse IP et le mot de passe sont demandés : le contrôleur lit ensuite automatiquement le nom, modèle, firmware et nombre de ports avant de créer l’équipement. Les champs de mot de passe ne sont jamais relus ni exposés par l’API. Le modèle détecté est conservé pour prendre en charge de futurs équipements TP-Link ; le pilote générique `model="Switch"` reste explicitement appliqué au TL-SG105PE.

## Diagnostic de lecture TP-Link

Les lectures convertissent explicitement les dataclasses `tplink-tool` (`SystemInfo`, `PortInfo`, `Dot1QVlanEntry`) vers des objets JSON. Toute réponse de forme inattendue est rejetée avec son type exact, et FastAPI écrit le traceback complet sous le logger `lfinfo.switches`; l’erreur n’est pas remplacée par des données vides. Les TL-SG105PE utilisent `model="Switch"` pour conserver la compatibilité connue, les modèles `*DE` utilisent `SwitchDE`, et les autres modèles sont laissés à l’auto-détection de `make_switch`.

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
- Les mots de passe des switches sont chiffrés dans SQLite, et ne sont jamais renvoyés par le frontend ou les routes API. Seuls les secrets administrateur et la clé de chiffrement résident dans `.env`.
- Chaque création, importation, test et modification de switch est journalisé. Avant une écriture de port/PVID autorisée, le backend enregistre une sauvegarde de la configuration lue dans SQLite. Les listes de sauvegardes et d’audit sont accessibles aux administrateurs via les routes authentifiées `/api/backups` et `/api/audit`.
- La modification des appartenances VLAN, PoE, et les compteurs TX/RX/erreurs ne sont pas disponibles car l’API actuelle ne les expose pas de façon validée sur les quatre firmwares.
- Placez FastAPI derrière HTTPS ou un tunnel SSH et limitez l’accès au VLAN d’administration.
