# AI CLI Dashboard (darkmedia-x_ai_cli)

Un tableau de bord interactif en Python pour lister, vérifier la version et lancer facilement vos différents assistants de code et outils d'intelligence artificielle en ligne de commande (CLI) sur Windows.

## 🚀 Fonctionnalités
- **Détection Automatique** : Recherche vos outils IA dans le `PATH` système ainsi que dans les dossiers d'installation courants (`AppData`, `.local/bin`, shims global NPM, etc.).
- **Vérification de Version** : Exécute automatiquement chaque outil en arrière-plan avec le flag `--version` pour afficher la version installée.
- **Raccourci Bureau** : Crée automatiquement un raccourci direct (« Mes CLI IA ») sur votre bureau lors du premier lancement.
- **Menu Interactif** : Permet de lancer directement l'outil de votre choix sans quitter la console actuelle.
- **Support des Emojis et Couleurs** : Rendu visuel propre et moderne avec des couleurs ANSI supportant le codage UTF-8.

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
