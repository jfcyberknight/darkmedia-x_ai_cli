# AI CLI Dashboard (darkmedia-x_ai_cli)

Un tableau de bord interactif en Python pour lister, vérifier la version et lancer facilement vos différents assistants de code et outils d'intelligence artificielle en ligne de commande (CLI) sur Windows.

## 🚀 Fonctionnalités
- **Détection Automatique** : Recherche vos outils IA dans le `PATH` système ainsi que dans les dossiers d'installation courants (`AppData`, `.local/bin`, shims global NPM, etc.).
- **Vérification de Version** : Exécute automatiquement chaque outil en arrière-plan avec le flag `--version` pour afficher la version installée.
- **🧠 Agent IA local (orchestrateur)** : Décrivez votre tâche en langage naturel (option `[A]`) et un cerveau local **pilote les CLIs comme des outils**, en headless : il choisit le bon CLI, rédige un sous-prompt précis, l'exécute (après votre confirmation), **récupère la sortie**, enchaîne d'autres étapes si besoin, puis synthétise une réponse. Il n'ouvre jamais de session interactive — le cerveau garde le contrôle. *Ex : « crée-moi un VPS gratuit sur Google » → délègue à `agy`.*
- **Raccourci Bureau** : Crée automatiquement un raccourci direct (« Mes CLI IA ») sur votre bureau lors du premier lancement.
- **Menu Interactif** : Permet de lancer directement l'outil de votre choix sans quitter la console actuelle.
- **Support des Emojis et Couleurs** : Rendu visuel propre et moderne avec des couleurs ANSI supportant le codage UTF-8.

## 🧠 Agent IA local — 100% autonome, sans abonnement cloud

L'option `[A]` du tableau de bord transforme le script en **agent orchestrateur** : vous posez une tâche en français, et un cerveau local **pilote les CLIs comme des outils** au lieu de simplement les ouvrir.

**Le cycle, à chaque étape :**
1. Le cerveau choisit le CLI le plus adapté et **rédige lui-même une consigne précise** pour lui.
2. Il vous montre le CLI + la consigne + la commande headless exacte, et **attend votre confirmation** (chaque appel est validé).
3. Il exécute le CLI en mode **non-interactif** (`claude -p`, `agy -p`, `opencode run`, `vibe -p`, …), affiche sa **sortie en direct** (streaming ligne par ligne), la **capture**, et l'analyse.
4. Il enchaîne éventuellement d'autres CLIs, puis **synthétise une réponse finale**.

Ainsi le cerveau ne « cède » jamais la main à une session interactive : il garde le contrôle et combine les résultats — c'est là toute la force de l'orchestration.

- **Cerveau local via [Ollama](https://ollama.com)** : les décisions sont prises par un modèle exécuté sur votre machine (aucune clé API, aucun abonnement, aucune donnée envoyée dans le cloud). Le serveur Ollama est démarré automatiquement si besoin.
- **Droits d'action** : après votre confirmation, le CLI s'exécute avec auto-approbation (`--dangerously-skip-permissions`, `--agent auto-approve`…) pour pouvoir réellement agir. Vous gardez la main grâce à la confirmation à chaque étape (limitée par `AGENT_MAX_STEPS`).
- **Repli par mots-clés** : si Ollama est absent ou éteint, un routage par mots-clés en une seule étape prend le relais — l'agent reste utilisable.
- **Comment ça marche** : chaque outil de `CLI_TOOLS` porte un champ `skills` (ses points forts) et un gabarit `headless` (comment l'appeler sans interface). Le modèle local reçoit ce contexte + l'historique des étapes et renvoie, en JSON, soit un appel d'outil, soit la réponse finale.

> ⚠️ **Note** : les CLIs délégués (Claude, agy, Vibe…) utilisent leurs propres identifiants/API. Assurez-vous qu'ils sont configurés pour que l'agent puisse les piloter.

## 🎚️ Choix du modèle par CLI (option `[M]`)

Chaque CLI peut tourner avec le **modèle de votre choix**, et par défaut avec **le modèle le moins cher** :

| CLI | Flag utilisé | Modèle par défaut (le moins cher) |
|---|---|---|
| `claude` | `--model` | `haiku` |
| `opencode` | `-m` | `opencode/deepseek-v4-flash-free` *(gratuit)* |
| `kilocode` / `kilo` | `-m` | `kilo/amazon/nova-micro-v1` |
| `agy` | `--model` | défaut natif d'agy *(choisissable dans `[M]`)* |
| `vibe` / `mistral` | — | non modifiable en CLI *(réglez-le via `vibe --setup`)* |

- **Configurer** : menu `[M]` → choisissez un CLI → `[L]` liste les modèles réellement disponibles (`<cli> models`) → tapez le numéro ou le nom exact (ou `d` pour revenir au défaut).
- **Persistance** : vos choix sont enregistrés dans `ai_cli_models.json` (à côté du script, ignoré par git). Ce fichier prime sur les défauts.
- Le modèle effectif s'affiche dans le tableau de bord (`[modèle: …]`, un `✱` marque un choix perso) et dans la commande headless montrée avant chaque appel de l'agent.

### 🤖 Choix automatique du modèle selon la tâche

Quand vous **n'avez pas épinglé** de modèle pour un CLI, l'agent choisit le **palier** en fonction de la complexité qu'il juge pour la sous-tâche :

| Complexité jugée | Palier | Exemples de modèle |
|---|---|---|
| **simple** (question courte, tâche directe) | `éco` | `haiku`, modèle gratuit, `nova-micro` |
| **complexe** (raisonnement, code élaboré, multi-étapes) | `costaud` | `sonnet`, `qwen3.7-max`, `claude-sonnet-latest` |

- Le palier retenu (`éco` / `costaud`) et la complexité jugée sont **affichés dans l'étape** avant confirmation.
- **Si vous épinglez un modèle via `[M]`**, il est **toujours utilisé** (l'agent ne le remplace pas) — pratique pour forcer un modèle précis.
- `agy` et `vibe`/`mistral` gèrent eux-mêmes leur modèle : pas de sélection automatique côté agent.

> 💡 Les modèles « éco » sont moins chers mais parfois moins performants. L'auto-sélection monte en `costaud` pour les tâches complexes ; sinon, épinglez le modèle voulu via `[M]`.

## ☁️ Session VPS éphémère (option `[V]`)

Un mode pour faire travailler l'agent dans une **VM cloud jetable** : provisionnement → clonage du repo → travail → **destruction complète**. Idéal pour ne rien laisser traîner sur votre machine ni dans le cloud.

**Cycle de vie** (pour un dépôt Git donné) :
1. Génération d'une **clé SSH éphémère**.
2. Création d'une VM **GCP `e2-micro`** (offre *Always Free*, zone `us-central1-a`).
3. Récupération de l'IP, **`git clone`** du repo sur la VM.
4. L'agent (ou vous, en SSH) travaille dans le repo.
5. **Destruction** de la VM **et de ses disques** (`--delete-disks=all`) + suppression de la clé locale.

- **DRY-RUN par défaut** : `[V]` affiche l'intégralité des commandes qui *seraient* exécutées (avec coût estimé ~0,01 $/2 h et notes de sécurité) **sans rien créer**. Il faut taper `EXECUTER` puis confirmer pour lancer réellement.
- **Prérequis pour l'exécution réelle** : le **Google Cloud SDK** (`gcloud`) installé et authentifié (`gcloud auth login`).
- **Sécurité** : clé SSH jetable, **destruction garantie** de la VM même en cas d'erreur (bloc `finally`) — jamais de VM facturée oubliée. Pour un repo privé, utilisez un token Git à portée limitée que vous révoquez ensuite.

> ⚠️ L'exécution réelle est **expérimentale** (non vérifiée contre un vrai projet GCP). Validez d'abord le plan en dry-run.

### Prérequis de l'agent (optionnels)
Pour le routage intelligent, installez Ollama et au moins un modèle :
```bash
# Installer Ollama (https://ollama.com/download), puis récupérer un modèle :
ollama pull gemma4
# Un modèle plus léger accélère le routage (ex. llama3.2:3b, qwen2.5:3b).
```
> Sans Ollama, l'agent reste utilisable grâce au repli par mots-clés.

## 🤖 Outils pris en charge
* **Antigravity CLI** (`agy`)
* **Claude Code** (`claude`)
* **OpenCode CLI** (`opencode`)
* **KiloCode CLI** (`kilocode`)
* **Kilo CLI** (`kilo`)
* **Mistral Vibe** (`vibe`)
* **Mistral CLI** (`mistral`)

---

## 🛠️ Installation & Utilisation

### Prérequis
- **Python 3.7+** (assurez-vous qu'il soit bien dans le PATH de Windows).

### Lancement
1. Double-cliquez sur le raccourci **Mes CLI IA** créé sur votre Bureau.
2. Ou lancez manuellement le script via votre terminal :
   ```bash
   python list_ai_clis.py
   ```

### Commandes utiles pour installer les outils manquants :
* **Claude Code** : 
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
* **Mistral Vibe** (via `uv` ou `pip`) :
  ```bash
  uv tool install mistral-vibe
  # ou
  pip install mistral-vibe
  ```
