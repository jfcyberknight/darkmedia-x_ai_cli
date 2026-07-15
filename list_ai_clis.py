#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
import ctypes
import time
import json
import re
import queue
import threading
import tempfile
import urllib.request
import urllib.error

def enable_ansi():
    if sys.platform == 'win32':
        try:
            kernel32 = ctypes.windll.kernel32
            stdout_handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode))
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)
        except Exception:
            pass

# Couleurs ANSI pour un rendu premium
enable_ansi()

# Reconfigurer la sortie standard pour supporter l'UTF-8 (emojis) sous Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"

# Outils CLI à détecter.
#   'skills'        : points forts de l'outil (fournis au cerveau local pour le routage).
#   'headless'      : gabarit d'arguments pour un appel NON-interactif (une commande ->
#                     une réponse capturable). '{prompt}' est remplacé par la consigne.
#   'auto_approve'  : arguments ajoutés pour donner à l'outil le droit d'exécuter des
#                     actions sans demander (seulement après confirmation, à chaque appel).
#   'model_flag'    : option pour imposer un modèle (None si le CLI ne le permet pas).
#   'default_model' : modèle par défaut « le moins cher » (None = défaut natif du CLI).
#                     Modifiable par l'utilisateur via le menu [M] (persisté dans un JSON).
#   'models_by_tier': paliers {'mini': ..., 'strong': ...} parmi lesquels l'agent choisit
#                     selon la complexité de la tâche (simple -> mini, complexe -> strong).
#                     Ignoré si l'utilisateur a épinglé un modèle via [M]. None = pas d'auto.
CLI_TOOLS = [
    {
        'key': 'agy',
        'name': 'Antigravity CLI',
        'command': 'agy',
        'desc': 'Assistant de code Google DeepMind (Antigravity)',
        'skills': ("Écosystème Google et Google Cloud (GCP) : créer/gérer des VPS et VMs "
                   "(Compute Engine), déployer sur Google Cloud, Firebase, Cloud Run, "
                   "essais/offres gratuites Google Cloud, services et APIs Google, Gemini."),
        'headless': ['-p', '{prompt}'],
        'auto_approve': ['--dangerously-skip-permissions'],
        'model_flag': '--model',
        'default_model': None,  # format du --model incertain -> laissé au défaut d'agy
        'models_by_tier': None,  # agy sélectionne son modèle Gemini en interne
    },
    {
        'key': 'claude',
        'name': 'Claude Code',
        'command': 'claude',
        'desc': 'Assistant de code Anthropic Claude Code',
        'skills': ("Agent de développement logiciel généraliste et polyvalent : écrire, "
                   "refactorer et déboguer du code multi-langages, analyser une base de "
                   "code, tâches d'ingénierie complexes, automatisation de dev. Choix par "
                   "défaut quand aucun autre outil n'est clairement plus adapté."),
        'headless': ['-p', '{prompt}'],
        'auto_approve': ['--dangerously-skip-permissions'],
        'model_flag': '--model',
        'default_model': 'haiku',  # le moins cher chez Anthropic
        'models_by_tier': {'mini': 'haiku', 'strong': 'sonnet'},
    },
    {
        'key': 'opencode',
        'name': 'OpenCode CLI',
        'command': 'opencode',
        'desc': 'Assistant de code OpenCode',
        'skills': ("Assistant de code open-source dans le terminal : édition de code, "
                   "solution flexible/agnostique du fournisseur, alternative libre."),
        'headless': ['run', '{prompt}'],
        'auto_approve': [],
        'model_flag': '-m',
        'default_model': 'opencode/deepseek-v4-flash-free',  # gratuit
        'models_by_tier': {'mini': 'opencode/deepseek-v4-flash-free',
                           'strong': 'opencode-go/qwen3.7-max'},
    },
    {
        'key': 'kilocode',
        'name': 'KiloCode CLI',
        'command': 'kilocode',
        'desc': 'Assistant de code KiloCode',
        'skills': ("Assistant de code KiloCode : génération et édition de code, "
                   "automatisation de tâches de développement."),
        'headless': ['run', '{prompt}'],
        'auto_approve': [],
        'model_flag': '-m',
        'default_model': 'kilo/amazon/nova-micro-v1',  # parmi les moins chers
        'models_by_tier': {'mini': 'kilo/amazon/nova-micro-v1',
                           'strong': 'kilo/~anthropic/claude-sonnet-latest'},
    },
    {
        'key': 'kilo',
        'name': 'Kilo CLI',
        'command': 'kilo',
        'desc': 'Raccourci/Alias de Kilo',
        'skills': "Variante/alias de KiloCode : génération et édition de code.",
        'headless': ['run', '{prompt}'],
        'auto_approve': [],
        'model_flag': '-m',
        'default_model': 'kilo/amazon/nova-micro-v1',  # parmi les moins chers
        'models_by_tier': {'mini': 'kilo/amazon/nova-micro-v1',
                           'strong': 'kilo/~anthropic/claude-sonnet-latest'},
    },
    {
        'key': 'vibe',
        'name': 'Mistral Vibe',
        'command': 'vibe',
        'desc': 'Assistant de code officiel Mistral AI (Vibe)',
        'skills': ("Assistant de code officiel Mistral AI : génération de code avec les "
                   "modèles Mistral, écosystème IA européen/français."),
        'headless': ['-p', '{prompt}', '--trust'],
        'auto_approve': ['--agent', 'auto-approve'],
        'model_flag': None,  # pas de --model en CLI : configuré via `vibe --setup`
        'default_model': None,
        'models_by_tier': None,
    },
    {
        'key': 'mistral',
        'name': 'Mistral CLI',
        'command': 'mistral',
        'desc': 'Interface en ligne de commande Mistral AI',
        'skills': ("Interface Mistral AI : chat et complétion de texte avec les modèles "
                   "Mistral, questions générales."),
        'headless': ['-p', '{prompt}', '--trust'],
        'auto_approve': ['--agent', 'auto-approve'],
        'model_flag': None,  # idem vibe
        'default_model': None,
        'models_by_tier': None,
    }
]

# Dossiers supplémentaires à fouiller si non présents dans le PATH
EXTRA_PATHS = [
    os.path.expandvars(r'%APPDATA%\npm'),
    os.path.expandvars(r'%USERPROFILE%\.local\bin'),
    os.path.expandvars(r'%LOCALAPPDATA%\agy\bin'),
]

# Choix de modèle par CLI, persisté à côté du script ({commande: "modèle"}).
# Une entrée ici prime sur 'default_model'. Éditable via le menu [M].
MODEL_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'ai_cli_models.json')

def load_model_overrides():
    try:
        with open(MODEL_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if v}
    except Exception:
        pass
    return {}

def save_model_overrides(overrides):
    try:
        with open(MODEL_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def find_tool_path(command_name):
    # Recherche dans le PATH standard
    path = shutil.which(command_name)
    if path:
        return path
        
    # Recherche dans les dossiers spécifiques
    extensions = ['', '.exe', '.cmd', '.bat', '.ps1']
    for folder in EXTRA_PATHS:
        if os.path.isdir(folder):
            for ext in extensions:
                full_path = os.path.join(folder, f"{command_name}{ext}")
                if os.path.isfile(full_path):
                    return full_path
    return None

def get_tool_version(path):
    if not path:
        return "N/A"
    try:
        use_shell = path.lower().endswith(('.cmd', '.bat'))
        
        if path.lower().endswith('.ps1'):
            res = subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', f"& '{path}' --version"],
                capture_output=True, text=True, timeout=3
            )
        else:
            res = subprocess.run(
                [path, '--version'],
                capture_output=True, text=True, shell=use_shell, timeout=3
            )
            
        out = res.stdout.strip()
        if not out and res.stderr:
            out = res.stderr.strip().split('\n')[0]
            
        if out:
            # Garder seulement la première ligne pour un affichage propre
            out = out.split('\n')[0].strip()
            return out
    except Exception:
        pass
    return "Inconnue"

# ============================================================================
#  AGENT DE ROUTAGE LOCAL
#  Choisit automatiquement le meilleur CLI IA pour une demande en langage
#  naturel. Utilise Ollama (100% local, sans abonnement cloud) comme cerveau,
#  avec un repli sur un routage par mots-clés si le serveur Ollama est absent.
# ============================================================================

OLLAMA_HOST = "http://127.0.0.1:11434"

def _http_get_json(url, timeout=3):
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))

def _http_post_json(url, payload, timeout=120):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))

def ollama_models():
    """Retourne la liste des modèles installés, [] si aucun, ou None si le
    serveur Ollama est injoignable."""
    try:
        data = _http_get_json(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return [m.get('name', '') for m in data.get('models', [])]
    except Exception:
        return None

def ensure_ollama():
    """S'assure que le serveur Ollama tourne. Le démarre si nécessaire.
    Retourne (ok: bool, model: str|None)."""
    models = ollama_models()
    if models is None and shutil.which('ollama'):
        # Serveur éteint : tenter de le lancer en arrière-plan.
        try:
            creationflags = 0
            if sys.platform == 'win32':
                # DETACHED_PROCESS | CREATE_NO_WINDOW
                creationflags = 0x00000008 | 0x08000000
            subprocess.Popen(['ollama', 'serve'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=creationflags)
        except Exception:
            pass
        for _ in range(12):  # attendre jusqu'à ~7s que le serveur réponde
            time.sleep(0.6)
            models = ollama_models()
            if models is not None:
                break
    if not models:
        return False, None
    # Préférer un modèle instruct/généraliste connu, sinon le premier disponible.
    for name in models:
        if any(k in name.lower() for k in ('gemma', 'qwen', 'llama', 'mistral', 'phi')):
            return True, name
    return True, models[0]

def route_with_ollama(query, installed):
    """Demande au modèle local quel CLI convient. Retourne un dict ou None."""
    ok, model = ensure_ollama()
    if not ok:
        return None
    tools_desc = "\n".join(f"- {t['command']} : {t['skills']}" for t in installed)
    valid = ", ".join(t['command'] for t in installed)
    prompt = (
        "Tu es un routeur qui sélectionne le meilleur outil CLI d'IA pour "
        "accomplir la tâche d'un utilisateur.\n\n"
        "Outils disponibles (seuls ceux-ci sont installés) :\n"
        f"{tools_desc}\n\n"
        f"Tâche de l'utilisateur : \"{query}\"\n\n"
        f"Choisis EXACTEMENT un outil dont la commande est parmi : {valid}.\n"
        'Réponds uniquement en JSON strict, sans texte autour : '
        '{"cli": "<commande>", "raison": "<phrase courte en français>"}'
    )
    try:
        data = _http_post_json(f"{OLLAMA_HOST}/api/generate", {
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "keep_alive": "5m",
            "options": {"temperature": 0},
        }, timeout=120)
        raw = data.get('response', '').strip()
        cli, reason = '', ''
        try:
            parsed = json.loads(raw)
            cli = str(parsed.get('cli', '')).strip().lower()
            reason = str(parsed.get('raison', '')).strip()
        except Exception:
            pass
        # 1) Correspondance exacte sur la commande.
        for t in installed:
            if t['command'].lower() == cli:
                return {'tool': t, 'reason': reason, 'engine': f'Ollama · {model}'}
        # 2) Repli tolérant : le modèle a parfois renvoyé le nom de l'outil ou
        #    un texte libre. On cherche une commande citée comme mot entier.
        tokens = set(re.findall(r'[a-zàâçéèêëîïôûùüÿñæœ]+', (cli + ' ' + raw).lower()))
        for t in installed:
            if t['command'].lower() in tokens or t['name'].lower() in raw.lower():
                return {'tool': t,
                        'reason': reason or "Choisi par le modèle local.",
                        'engine': f'Ollama · {model}'}
    except Exception:
        return None
    return None

# Routage de secours par mots-clés (utilisé si Ollama est indisponible).
# Ordre = priorité : le premier outil installé dont un mot-clé apparaît gagne.
KEYWORD_ROUTES = [
    ('agy', ['google', 'gcp', 'vps', 'compute engine', 'gce', 'firebase',
             'cloud run', 'google cloud', 'antigravity', 'deepmind', 'gemini']),
    ('vibe', ['mistral', 'vibe']),
    ('mistral', ['mistral cli']),
    ('opencode', ['opencode', 'open source', 'open-source']),
    ('kilocode', ['kilocode', 'kilo code']),
    ('kilo', ['kilo']),
    ('claude', ['claude', 'anthropic', 'refactor', 'debug', 'bug', 'code',
                'coder', 'programme', 'développe', 'developpe', 'script',
                'fonction', 'test']),
]

def route_with_keywords(query, installed):
    q = query.lower()
    by_cmd = {t['command']: t for t in installed}
    for cmd, keywords in KEYWORD_ROUTES:
        if cmd in by_cmd and any(k in q for k in keywords):
            return {'tool': by_cmd[cmd],
                    'reason': "Mot-clé reconnu dans la demande.",
                    'engine': 'Règles (mots-clés)'}
    # Défaut : Claude Code (généraliste) sinon le premier outil installé.
    if 'claude' in by_cmd:
        return {'tool': by_cmd['claude'],
                'reason': "Choix par défaut (agent généraliste).",
                'engine': 'Règles (défaut)'}
    if installed:
        return {'tool': installed[0],
                'reason': "Choix par défaut (premier outil installé).",
                'engine': 'Règles (défaut)'}
    return None

def route_query(query, scanned):
    """Choisit le meilleur CLI installé pour la demande. Ollama d'abord,
    repli sur les mots-clés."""
    installed = [t for t in scanned if t['installed']]
    if not installed:
        return None
    return route_with_ollama(query, installed) or route_with_keywords(query, installed)

def copy_to_clipboard(text):
    """Copie du texte dans le presse-papier Windows (best-effort)."""
    if sys.platform != 'win32':
        return False
    try:
        subprocess.run('clip', input=text, text=True, shell=True,
                       encoding='utf-8', errors='replace')
        return True
    except Exception:
        return False

# ---- Pilotage headless des CLIs (le cerveau les utilise comme des outils) ----

def build_headless_argv(tool, prompt, with_actions=True):
    """Construit la ligne de commande NON-interactive pour un outil, en
    injectant le modèle choisi si le CLI le permet."""
    argv = [tool['path']]
    model = tool.get('model')
    flag = tool.get('model_flag')
    if model and flag:  # imposer le modèle (ex. --model haiku, -m provider/model)
        argv += [flag, model]
    argv += [a.replace('{prompt}', prompt) for a in tool.get('headless', ['{prompt}'])]
    if with_actions:
        argv += tool.get('auto_approve', [])
    return argv

def resolve_call_model(tool, complexity):
    """Choisit le modèle d'un appel selon la complexité jugée par le cerveau.
    Retourne (modèle, étiquette). Un modèle épinglé par l'utilisateur ([M])
    a toujours la priorité — l'agent ne l'écrase pas."""
    if tool.get('model_is_custom'):
        return tool.get('model'), 'épinglé'
    tiers = tool.get('models_by_tier') or {}
    if str(complexity).lower().startswith('complex') and tiers.get('strong'):
        return tiers['strong'], 'costaud'
    if tiers.get('mini'):
        return tiers['mini'], 'éco'
    return tool.get('model'), 'défaut'

def _quote_arg(a):
    if a == '' or any(c in a for c in ' "\t&|<>^'):
        return '"' + a.replace('"', "'") + '"'
    return a

def display_argv(argv):
    """Version lisible/quotée d'un argv pour affichage à l'utilisateur."""
    # On affiche le nom court de l'exécutable plutôt que son chemin complet.
    shown = list(argv)
    shown[0] = os.path.basename(shown[0])
    return ' '.join(_quote_arg(a) for a in shown)

def run_cli_headless(tool, prompt, timeout=300, with_actions=True, stream=False, indent="     "):
    """Exécute un CLI en mode non-interactif et capture sa sortie.
    Si stream=True, affiche la sortie en direct (ligne par ligne) pendant
    l'exécution. Retourne {'ok': bool, 'output': str, 'code': int}.

    La lecture se fait dans un thread + file d'attente : le délai (timeout)
    est ainsi respecté même si le CLI ne produit aucune sortie."""
    argv = build_headless_argv(tool, prompt, with_actions)
    path = tool['path']
    use_shell = path.lower().endswith(('.cmd', '.bat'))
    cmd = ' '.join(_quote_arg(a) for a in argv) if use_shell else argv
    try:
        proc = subprocess.Popen(
            cmd, shell=use_shell,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True, encoding='utf-8', errors='replace', bufsize=1,
        )
    except Exception as e:
        return {'ok': False, 'output': f"<erreur de lancement : {e}>", 'code': -1}

    q = queue.Queue()

    def _reader():
        try:
            for line in proc.stdout:
                q.put(line)
        except Exception:
            pass
        finally:
            q.put(None)  # sentinelle de fin

    threading.Thread(target=_reader, daemon=True).start()

    collected = []
    start = time.monotonic()
    timed_out = False
    while True:
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            timed_out = True
            break
        try:
            line = q.get(timeout=min(1.0, remaining))
        except queue.Empty:
            continue  # rien reçu depuis 1s : on revérifie le délai
        if line is None:
            break  # le CLI a terminé
        line = line.rstrip('\r\n')
        collected.append(line)
        if stream:
            print(f"{indent}{C_DIM}{line}{C_RESET}")

    if timed_out:
        try:
            proc.kill()
        except Exception:
            pass
        collected.append(f"<délai dépassé après {timeout}s — l'outil a été interrompu>")
        if stream:
            print(f"{indent}{C_YELLOW}<délai dépassé — interrompu>{C_RESET}")
    try:
        proc.wait(timeout=5)
    except Exception:
        pass

    code = proc.returncode if proc.returncode is not None else -1
    output = "\n".join(collected).strip()
    return {'ok': (code == 0 and not timed_out), 'output': output, 'code': code}

def _history_text(history):
    if not history:
        return "(aucune étape effectuée pour l'instant)"
    parts = []
    for i, h in enumerate(history, 1):
        out = h['output']
        if len(out) > 1200:
            out = out[:1200] + " …(tronqué)"
        parts.append(f"Étape {i} — appel de `{h['cli']}` avec la consigne : {h['prompt']}\n"
                     f"Résultat obtenu :\n{out}")
    return "\n\n".join(parts)

def brain_next_action(query, installed, history, model):
    """Demande au cerveau local la prochaine action : appeler un outil, ou
    terminer avec une réponse. Retourne un dict ou None."""
    tools_desc = "\n".join(f"- {t['command']} : {t['skills']}" for t in installed)
    valid = ", ".join(t['command'] for t in installed)
    prompt = (
        "Tu es un cerveau orchestrateur. Pour accomplir la demande de l'utilisateur, tu "
        "délègues des sous-tâches à des outils CLI d'IA spécialisés, tu observes leurs "
        "résultats, puis tu synthétises une réponse.\n\n"
        f"Demande de l'utilisateur : \"{query}\"\n\n"
        f"Outils disponibles :\n{tools_desc}\n\n"
        f"Historique des étapes :\n{_history_text(history)}\n\n"
        "Choisis la PROCHAINE action et réponds UNIQUEMENT en JSON strict :\n"
        '- Pour déléguer à un outil : '
        '{"action":"call","cli":"<commande>","prompt":"<consigne précise en français>",'
        '"complexite":"simple|complexe"}\n'
        '- Si les résultats suffisent à répondre : '
        '{"action":"final","message":"<réponse finale claire pour l\'utilisateur>"}\n\n'
        f"Le champ \"cli\" doit valoir EXACTEMENT l'une de : {valid}.\n"
        "\"complexite\" évalue la sous-tâche : \"simple\" (question courte, tâche directe "
        "-> modèle économique) ou \"complexe\" (raisonnement poussé, code élaboré, "
        "multi-étapes -> modèle plus puissant).\n"
        "Ne rappelle pas un outil pour une sous-tâche déjà traitée ; termine dès que possible."
    )
    try:
        data = _http_post_json(f"{OLLAMA_HOST}/api/generate", {
            "model": model, "prompt": prompt, "format": "json",
            "stream": False, "keep_alive": "5m", "options": {"temperature": 0.2},
        }, timeout=180)
        d = json.loads(data.get('response', '').strip())
    except Exception:
        return None
    action = str(d.get('action', '')).strip().lower()
    if action == 'final':
        return {'action': 'final', 'message': str(d.get('message', '')).strip()}
    if action == 'call':
        cli = str(d.get('cli', '')).strip().lower()
        sub = str(d.get('prompt', '')).strip()
        complexity = str(d.get('complexite', 'simple')).strip().lower()
        complexity = 'complexe' if complexity.startswith('complex') else 'simple'
        by_cmd = {t['command'].lower(): t for t in installed}
        tool = by_cmd.get(cli)
        if tool is None:  # repli tolérant : commande citée quelque part dans la réponse
            raw = json.dumps(d, ensure_ascii=False).lower()
            for t in installed:
                if re.search(rf'\b{re.escape(t["command"].lower())}\b', raw):
                    tool = t
                    break
        if tool is not None:
            return {'action': 'call', 'tool': tool, 'prompt': sub or query,
                    'complexity': complexity}
    return None

def brain_synthesize(query, history, model):
    """Force une réponse finale à partir de l'historique (fin de boucle)."""
    prompt = (
        "Tu es un cerveau orchestrateur. À partir des résultats collectés auprès des "
        "outils, rédige une réponse finale claire et utile, en français.\n\n"
        f"Demande initiale : \"{query}\"\n\n"
        f"Résultats des outils :\n{_history_text(history)}\n\n"
        'Réponds UNIQUEMENT en JSON strict : {"message":"<ta réponse finale>"}'
    )
    try:
        data = _http_post_json(f"{OLLAMA_HOST}/api/generate", {
            "model": model, "prompt": prompt, "format": "json",
            "stream": False, "keep_alive": "5m", "options": {"temperature": 0.3},
        }, timeout=180)
        return str(json.loads(data.get('response', '').strip()).get('message', '')).strip()
    except Exception:
        return ""

def list_cli_models(tool):
    """Retourne la liste des modèles disponibles pour un CLI (ou None)."""
    cmd = tool['command']
    if cmd == 'claude':  # pas de sous-commande `models` : alias connus
        return ['haiku', 'sonnet', 'opus', '(ou un ID complet, ex. claude-haiku-4-5)']
    if tool.get('model_flag') is None:
        return None
    path = tool['path']
    try:
        if path.lower().endswith(('.cmd', '.bat')):
            res = subprocess.run(f'"{path}" models', shell=True, capture_output=True,
                                 text=True, timeout=30, stdin=subprocess.DEVNULL,
                                 encoding='utf-8', errors='replace')
        else:
            res = subprocess.run([path, 'models'], capture_output=True, text=True,
                                 timeout=30, stdin=subprocess.DEVNULL,
                                 encoding='utf-8', errors='replace')
        lines = [l.strip() for l in (res.stdout or '').splitlines() if l.strip()]
        return lines or None
    except Exception:
        return None

def configure_models(scanned):
    """Menu [M] : choisir le modèle utilisé par chaque CLI (persisté en JSON)."""
    installed = [t for t in scanned if t['installed']]
    overrides = load_model_overrides()
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"\n{C_CYAN}  ┌────────────────────────────────────────────────────────┐{C_RESET}")
        print(f"{C_CYAN}  │      ⚙  MODÈLE PAR CLI  (défaut = le moins cher)       │{C_RESET}")
        print(f"{C_CYAN}  └────────────────────────────────────────────────────────┘{C_RESET}\n")
        for idx, t in enumerate(installed, 1):
            if t.get('model_flag') is None:
                cur = f"{C_DIM}non configurable en CLI (voir la config du CLI){C_RESET}"
            else:
                mdl = overrides.get(t['command']) or t.get('default_model')
                if mdl:
                    tag = "choisi" if t['command'] in overrides else "défaut"
                    cur = f"{C_CYAN}{mdl}{C_RESET} {C_DIM}({tag}){C_RESET}"
                else:
                    cur = f"{C_DIM}défaut natif du CLI{C_RESET}"
            print(f"  {C_BOLD}[{idx}]{C_RESET} {t['name']:<16} : {cur}")
        print(f"\n  {C_BOLD}[Q]{C_RESET} Retour au tableau de bord")
        try:
            choice = input(f"\n  {C_CYAN}👉 Numéro du CLI à configurer (Q = retour) : {C_RESET}").strip().lower()
        except KeyboardInterrupt:
            return
        if choice in ('q', ''):
            return
        try:
            idx = int(choice) - 1
        except ValueError:
            continue
        if not (0 <= idx < len(installed)):
            continue
        tool = installed[idx]
        if tool.get('model_flag') is None:
            print(f"\n  {C_YELLOW}⚠ {tool['name']} ne permet pas de choisir le modèle en ligne "
                  f"de commande.{C_RESET}")
            print(f"  {C_DIM}(Configure-le dans l'outil, ex. « vibe --setup ».){C_RESET}")
            time.sleep(2.5)
            continue

        models = None
        try:
            ans = input(f"\n  {C_CYAN}[L] lister les modèles disponibles, ou Entrée pour saisir "
                        f"directement : {C_RESET}").strip().lower()
        except KeyboardInterrupt:
            continue
        if ans == 'l':
            print(f"  {C_DIM}⏳ Récupération des modèles ({tool['command']} models)...{C_RESET}")
            models = list_cli_models(tool)
            if models:
                for i, mdl in enumerate(models, 1):
                    print(f"     {C_DIM}{i:>3}.{C_RESET} {mdl}")
            else:
                print(f"  {C_YELLOW}(Liste indisponible — saisis le nom du modèle à la main.){C_RESET}")

        cur_default = tool.get('default_model') or "défaut natif"
        try:
            val = input(f"\n  {C_CYAN}Modèle pour {tool['name']} (numéro de la liste, nom exact, "
                        f"'d' = défaut « {cur_default} », vide = annuler) : {C_RESET}").strip()
        except KeyboardInterrupt:
            continue
        if not val:
            continue
        if val.lower() in ('d', 'defaut', 'défaut', 'reset'):
            overrides.pop(tool['command'], None)
        else:
            picked = None
            if models and val.isdigit():
                n = int(val)
                if 1 <= n <= len(models):
                    picked = models[n - 1]
            chosen = picked or val
            if chosen.startswith('('):  # ligne d'aide, pas un vrai modèle
                print(f"  {C_YELLOW}Sélection invalide.{C_RESET}")
                time.sleep(1.5)
                continue
            overrides[tool['command']] = chosen
        if save_model_overrides(overrides):
            print(f"\n  {C_GREEN}✔ Enregistré.{C_RESET}")
        else:
            print(f"\n  {C_RED}⚠ Échec de l'enregistrement.{C_RESET}")
        time.sleep(1.2)

def create_desktop_shortcut():
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    shortcut_path = os.path.join(desktop, 'Mes CLI IA.lnk')
    script_path = os.path.abspath(__file__)
    python_exe = sys.executable
    
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
    icon_location = f"{icon_path}, 0" if os.path.exists(icon_path) else "cmd.exe, 0"
    
    ps_cmd = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{python_exe}"
    $Shortcut.Arguments = '"{script_path}"'
    $Shortcut.WorkingDirectory = "{os.path.dirname(script_path)}"
    $Shortcut.Description = "Tableau de bord de mes CLI IA"
    $Shortcut.IconLocation = "{icon_location}"
    $Shortcut.Save()
    """
    try:
        subprocess.run(['powershell', '-NoProfile', '-Command', ps_cmd], capture_output=True)
        return shortcut_path
    except Exception:
        return None

def check_and_create_shortcut():
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    shortcut_path = os.path.join(desktop, 'Mes CLI IA.lnk')
    if not os.path.exists(shortcut_path):
        created_path = create_desktop_shortcut()
        if created_path:
            print(f"{C_GREEN}✨ Raccourci créé avec succès sur le bureau ! ({shortcut_path}){C_RESET}\n")
        else:
            print(f"{C_YELLOW}⚠ Impossible de créer le raccourci sur le bureau automatiquement.{C_RESET}\n")

def scan_tools():
    scanned = []
    overrides = load_model_overrides()
    for tool in CLI_TOOLS:
        path = find_tool_path(tool['command'])
        version = get_tool_version(path) if path else "N/A"
        # Modèle effectif : choix utilisateur (JSON) sinon défaut « moins cher ».
        effective_model = overrides.get(tool['command']) or tool.get('default_model')
        scanned.append({
            'name': tool['name'],
            'command': tool['command'],
            'desc': tool['desc'],
            'skills': tool.get('skills', ''),
            'headless': tool.get('headless', ['{prompt}']),
            'auto_approve': tool.get('auto_approve', []),
            'model_flag': tool.get('model_flag'),
            'default_model': tool.get('default_model'),
            'models_by_tier': tool.get('models_by_tier'),
            'model': effective_model,
            'model_is_custom': tool['command'] in overrides,
            'path': path,
            'version': version,
            'installed': path is not None
        })
    return scanned

def print_dashboard(scanned):
    # En-tête premium
    print(f"\n{C_CYAN}  ┌────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_CYAN}  │             🤖 TABLEAU DE BORD DE MES CLI IA 🤖        │{C_RESET}")
    print(f"{C_CYAN}  └────────────────────────────────────────────────────────┘{C_RESET}\n")
    
    # Affichage du tableau
    print(f"  {C_BOLD}{'N°':<4} | {'Nom du CLI':<17} | {'Statut':<12} | {'Version':<18} | {'Commande':<10}{C_RESET}")
    print(f"  {C_DIM}-----+-------------------+--------------+--------------------+----------{C_RESET}")
    
    installed_count = 0
    for idx, tool in enumerate(scanned, 1):
        if tool['installed']:
            installed_count += 1
            status_str = f"{C_GREEN}Installé{C_RESET}"
            version_str = f"{C_CYAN}{tool['version']}{C_RESET}"
            idx_str = f"[{idx}]"
            name_str = f"{C_BOLD}{tool['name']}{C_RESET}"
        else:
            status_str = f"{C_RED}Absent{C_RESET}"
            version_str = f"{C_DIM}N/A{C_RESET}"
            idx_str = f" {C_DIM}x{C_RESET} "
            name_str = f"{C_DIM}{tool['name']}{C_RESET}"
            
        print(f"  {idx_str:<4} | {name_str:<17} | {status_str:<12} | {version_str:<18} | {C_YELLOW if tool['installed'] else C_DIM}{tool['command']:<10}{C_RESET}")
        
        # Sous-titre
        if tool['installed']:
            if tool.get('model_flag') and tool.get('model'):
                mtag = "✱" if tool.get('model_is_custom') else ""
                minfo = f" {C_MAGENTA}[modèle: {tool['model']}{mtag}]{C_DIM}"
            else:
                minfo = ""
            print(f"       {C_DIM}↳ {tool['desc']}{minfo} (Path: {tool['path']}){C_RESET}")
        else:
            print(f"       {C_DIM}↳ {tool['desc']} (Non détecté){C_RESET}")
            
    print(f"\n  {C_DIM}------------------------------------------------------------------------{C_RESET}")
    return installed_count

def run_tool(tool, prompt=None):
    path = tool['path']
    cmd_name = tool['command']
    print(f"\n{C_CYAN}⚡ Lancement de {tool['name']} ({cmd_name})...{C_RESET}")
    print(f"{C_DIM}Dossier de travail actuel : {os.getcwd()}{C_RESET}")
    if prompt:
        print(f"{C_DIM}Demande transmise : {prompt}{C_RESET}")
    print(f"{C_DIM}Appuyez sur Ctrl+C ou quittez l'outil pour revenir au tableau de bord.{C_RESET}\n")
    time.sleep(0.5)

    try:
        # Exécuter de manière interactive, en transmettant éventuellement la
        # demande de l'agent comme argument positionnel.
        if path.lower().endswith(('.cmd', '.bat')):
            cmd = f'"{path}" "{prompt}"' if prompt else f'"{path}"'
            subprocess.run(cmd, shell=True)
        elif path.lower().endswith('.ps1'):
            args = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path]
            if prompt:
                args.append(prompt)
            subprocess.run(args)
        else:
            subprocess.run([path, prompt] if prompt else [path])
    except KeyboardInterrupt:
        # Capturer l'interruption Ctrl+C si elle se propage à Python
        pass
    except Exception as e:
        print(f"{C_RED}⚠ Erreur lors du lancement de {cmd_name} : {e}{C_RESET}")
        time.sleep(2)
        
    print(f"\n{C_GREEN}✓ Retour au tableau de bord de {tool['name']}.{C_RESET}")
    time.sleep(1.2)

# Comment se reconnecter à chaque CLI (affiché en cas d'échec d'authentification).
AUTH_HINTS = {
    'claude':   "lance `claude` puis tape `/login`",
    'agy':      "lance `agy` et reconnecte ton compte Google",
    'opencode': "lance `opencode auth login` (ou `opencode providers`)",
    'kilocode': "lance `kilocode auth` pour reconnecter le fournisseur",
    'kilo':     "lance `kilo auth` pour reconnecter le fournisseur",
    'vibe':     "lance `vibe --setup` pour reconfigurer la clé API",
    'mistral':  "lance `mistral --setup` pour reconfigurer la clé API",
}

_AUTH_PATTERNS = (
    'failed to authenticate', 'oauth', 'session expired', 'token expired',
    'expired token', 'not authenticated', 'unauthorized', '401',
    'authentication failed', 'authentication required', 'auth required',
    'invalid api key', 'no api key', 'api key not', 'missing api key',
    'please log in', 'please login', 'not logged in', 'login required',
    'log in to', 'sign in to', 'no credentials', 'invalid credentials',
)

def is_auth_error(text):
    """Vrai si la sortie d'un CLI ressemble à un échec d'authentification."""
    if not text:
        return False
    low = text.lower()
    return any(p in low for p in _AUTH_PATTERNS)

# Commande de connexion (interactive) par CLI : args ajoutés après l'exécutable.
# [] = lancer le CLI tel quel en interactif (cas où il n'a pas de sous-commande login).
AUTH_COMMANDS = {
    'claude':   ['auth', 'login'],
    'opencode': ['auth', 'login'],
    'kilocode': ['auth', 'login'],
    'kilo':     ['auth', 'login'],
    'vibe':     ['--setup'],
    'mistral':  ['--setup'],
    'agy':      [],
}

def run_cli_interactive(tool, extra_args):
    """Lance un CLI en mode INTERACTIF (stdin/stdout hérités) pour que
    l'utilisateur puisse se connecter (OAuth/navigateur, clé API…)."""
    path = tool['path']
    try:
        if path.lower().endswith(('.cmd', '.bat')):
            cmdline = ' '.join(_quote_arg(a) for a in [path] + list(extra_args))
            subprocess.run(cmdline, shell=True)
        elif path.lower().endswith('.ps1'):
            subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                            '-File', path] + list(extra_args))
        else:
            subprocess.run([path] + list(extra_args))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"  {C_RED}Erreur pendant la connexion : {e}{C_RESET}")

AGENT_MAX_STEPS = 5  # garde-fou : nombre maxi d'appels CLI par demande

def ask_agent(scanned):
    """Orchestrateur : le cerveau local pilote les CLIs en mode headless
    (sans les ouvrir), capture leurs sorties, enchaîne les étapes et synthétise.
    Chaque appel CLI est confirmé par l'utilisateur avant exécution."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\n{C_MAGENTA}  ┌────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_MAGENTA}  │     🧠 AGENT IA LOCAL — orchestrateur (headless)       │{C_RESET}")
    print(f"{C_MAGENTA}  └────────────────────────────────────────────────────────┘{C_RESET}\n")
    print(f"  {C_DIM}Le cerveau appelle les CLIs comme des outils, récupère leurs réponses{C_RESET}")
    print(f"  {C_DIM}et enchaîne les étapes. Tu confirmes chaque appel avant exécution.{C_RESET}")
    print(f"  {C_DIM}Exemple : « crée-moi un VPS gratuit sur Google »{C_RESET}\n")

    installed = [t for t in scanned if t['installed']]
    if not installed:
        print(f"  {C_RED}⚠ Aucun CLI IA installé n'est disponible.{C_RESET}")
        time.sleep(2)
        return

    try:
        query = input(f"  {C_CYAN}🗣  Ta demande (vide = retour) : {C_RESET}").strip()
    except KeyboardInterrupt:
        return
    if not query:
        return

    ok, model = ensure_ollama()
    if ok:
        print(f"\n  {C_DIM}Cerveau : Ollama · {model}{C_RESET}")
    else:
        print(f"\n  {C_YELLOW}Cerveau local (Ollama) indisponible → routage de secours par "
              f"mots-clés, une seule étape.{C_RESET}")

    history = []          # [{cli, prompt, output}]
    final_message = None
    unavailable = set()   # CLIs écartés pour la session (ex. non authentifiés)

    for step in range(1, AGENT_MAX_STEPS + 1):
        # CLIs encore utilisables (on retire ceux dont l'auth a échoué).
        available = [t for t in installed if t['command'] not in unavailable]
        if not available:
            print(f"\n  {C_RED}⚠ Plus aucun CLI authentifié n'est disponible pour continuer.{C_RESET}")
            break

        # 1) Décider de la prochaine action.
        decision = None
        if ok:
            print(f"\n  {C_DIM}⏳ Le cerveau réfléchit à la prochaine étape...{C_RESET}")
            decision = brain_next_action(query, available, history, model)
        if decision is None:
            # Repli : sans cerveau, on route une seule fois par mots-clés.
            if not history:
                r = route_with_keywords(query, available)
                if r:
                    decision = {'action': 'call', 'tool': r['tool'], 'prompt': query}
            if decision is None:
                break

        # 2) Terminer si le cerveau a une réponse.
        if decision['action'] == 'final':
            final_message = decision.get('message') or ""
            break

        # 3) Sinon, préparer l'appel CLI et demander confirmation.
        tool = decision['tool']
        sub = decision['prompt']
        complexity = decision.get('complexity', 'simple')
        # Modèle choisi selon la complexité (sauf si l'utilisateur l'a épinglé).
        chosen_model, tier_label = resolve_call_model(tool, complexity)
        tool['model'] = chosen_model  # injecté dans build_headless_argv
        argv = build_headless_argv(tool, sub, with_actions=True)
        print(f"\n  {C_CYAN}━━ Étape {step} ━━{C_RESET}")
        print(f"  {C_GREEN}Outil{C_RESET}    : {C_BOLD}{tool['name']}{C_RESET} "
              f"({C_YELLOW}{tool['command']}{C_RESET})")
        if tool.get('model_flag') and chosen_model:
            print(f"  {C_GREEN}Modèle{C_RESET}   : {C_CYAN}{chosen_model}{C_RESET} "
                  f"{C_DIM}(palier {tier_label} · tâche jugée « {complexity} »){C_RESET}")
        print(f"  {C_GREEN}Consigne{C_RESET} : {sub}")
        print(f"  {C_GREEN}Commande{C_RESET} : {C_DIM}{display_argv(argv)}{C_RESET}")
        if tool.get('auto_approve'):
            print(f"  {C_YELLOW}⚠ S'exécutera avec droits d'action (auto-approbation des outils).{C_RESET}")

        try:
            confirm = input(f"  {C_CYAN}👉 Exécuter cette étape ? "
                            f"[{C_BOLD}O{C_RESET}{C_CYAN}/n] : {C_RESET}").strip().lower()
        except KeyboardInterrupt:
            break
        if confirm in ('n', 'non', 'no'):
            print(f"  {C_YELLOW}Étape refusée — arrêt de l'orchestration.{C_RESET}")
            break

        # 4) Exécuter en headless, en affichant la sortie EN DIRECT.
        print(f"\n  {C_DIM}⏳ Exécution — sortie en direct de {tool['command']} "
              f"(peut prendre un moment) :{C_RESET}")
        res = run_cli_headless(tool, sub, timeout=300, with_actions=True, stream=True)
        out = res['output'] or "(aucune sortie)"
        tag = f"{C_GREEN}OK{C_RESET}" if res['ok'] else f"{C_RED}échec (code {res['code']}){C_RESET}"
        print(f"\n  {C_CYAN}━━ Fin de l'étape {step} [{tag}{C_CYAN}] ━━{C_RESET}")

        # Échec d'authentification : proposer de se reconnecter tout de suite,
        # sinon écarter ce CLI et laisser le cerveau basculer vers un autre.
        if not res['ok'] and is_auth_error(out):
            hint = AUTH_HINTS.get(tool['command'], "reconnecte-toi à cet outil")
            print(f"\n  {C_RED}🔑 {tool['name']} n'est pas authentifié.{C_RESET} "
                  f"{C_YELLOW}(→ {hint}){C_RESET}")
            try:
                do_auth = input(f"  {C_CYAN}👉 Te reconnecter à {tool['name']} maintenant ? "
                                f"[{C_BOLD}O{C_RESET}{C_CYAN}/n] : {C_RESET}").strip().lower()
            except KeyboardInterrupt:
                do_auth = 'n'

            if do_auth not in ('n', 'non', 'no'):
                auth_args = AUTH_COMMANDS.get(tool['command'], [])
                shown = (tool['command'] + ' ' + ' '.join(auth_args)).strip()
                print(f"\n  {C_CYAN}⚙ Ouverture de la connexion : {shown}{C_RESET}")
                if not auth_args:
                    print(f"  {C_DIM}Connecte-toi, puis quitte l'outil (Ctrl+C) pour revenir.{C_RESET}")
                print(f"  {C_DIM}(suis les instructions — navigateur/clé API — puis reviens ici){C_RESET}\n")
                run_cli_interactive(tool, auth_args)

                # Réessayer la même étape une fois la connexion faite.
                print(f"\n  {C_DIM}↻ Reconnexion terminée — je réessaie l'étape {step}...{C_RESET}")
                res = run_cli_headless(tool, sub, timeout=300, with_actions=True, stream=True)
                out = res['output'] or "(aucune sortie)"
                tag = f"{C_GREEN}OK{C_RESET}" if res['ok'] else f"{C_RED}échec (code {res['code']}){C_RESET}"
                print(f"\n  {C_CYAN}━━ Réessai étape {step} [{tag}{C_CYAN}] ━━{C_RESET}")
                if res['ok'] or not is_auth_error(out):
                    history.append({'cli': tool['command'], 'prompt': sub, 'output': out})
                    if not ok:
                        break
                    continue
                print(f"  {C_YELLOW}Toujours pas authentifié — je passe à un autre CLI.{C_RESET}")

            # Reconnexion refusée ou toujours en échec : écarter ce CLI.
            unavailable.add(tool['command'])
            history.append({'cli': tool['command'], 'prompt': sub,
                            'output': (f"ÉCHEC : {tool['name']} n'est pas authentifié "
                                       f"(non utilisable pour cette session). Choisis un AUTRE outil.")})
            if ok:
                continue  # laisser le cerveau re-décider avec un autre CLI
            break         # sans cerveau : on s'arrête

        history.append({'cli': tool['command'], 'prompt': sub, 'output': out})

        if not ok:  # pas de cerveau → une seule étape
            break

    # 5) Réponse finale : celle du cerveau, sinon une synthèse forcée.
    if final_message is None and history and ok:
        print(f"\n  {C_DIM}⏳ Synthèse finale...{C_RESET}")
        final_message = brain_synthesize(query, history, model)

    if final_message:
        print(f"\n  {C_MAGENTA}🧠 Réponse de l'agent :{C_RESET}")
        print(f"  {final_message}")
    elif history:
        print(f"\n  {C_DIM}Vois les résultats des étapes ci-dessus.{C_RESET}")
    else:
        print(f"\n  {C_RED}⚠ Aucune action n'a pu être effectuée pour cette demande.{C_RESET}")

    try:
        input(f"\n  {C_DIM}Appuyez sur Entrée pour revenir au tableau de bord...{C_RESET}")
    except KeyboardInterrupt:
        pass

# ============================================================================
#  MODE VPS ÉPHÉMÈRE (cloud)
#  Provisionne une VM GCP jetable, y clone un repo, laisse l'agent travailler,
#  puis DÉTRUIT la VM (+ disques). DRY-RUN par défaut : rien n'est créé tant
#  que l'utilisateur n'a pas explicitement validé. La destruction est garantie
#  (bloc finally) pour ne jamais laisser une VM facturée en vie.
# ============================================================================

VPS_CONFIG = {
    'zone': 'us-central1-a',            # zone éligible à l'offre gratuite
    'machine_type': 'e2-micro',         # Always Free
    'image_family': 'debian-12',
    'image_project': 'debian-cloud',
    'ssh_user': 'aiagent',
    'name_prefix': 'ai-ephemeral',
    'work_dir': '~/work',
    'default_repo': 'https://github.com/jfcyberknight/apartment-repair-tracker.git',
}

def build_vps_plan(c):
    """Construit le plan (label, note, commande affichable) du cycle de vie."""
    pub = f'{c["key_path"]}.pub'
    return [
        ("1. Clé SSH éphémère",
         "Paire de clés jetable, supprimée en fin de session.",
         f'ssh-keygen -t ed25519 -f "{c["key_path"]}" -N "" -C "ai-ephemeral"'),
        ("2. Création VM (e2-micro · Free Tier)",
         f'Instance jetable dans {c["zone"]}.',
         f'gcloud compute instances create {c["name"]} --zone={c["zone"]} '
         f'--machine-type={c["machine_type"]} --image-family={c["image_family"]} '
         f'--image-project={c["image_project"]} '
         f'--metadata=ssh-keys="{c["ssh_user"]}:$(cat {pub})"'),
        ("3. Récupération de l'IP externe",
         "Lecture de l'IP publique une fois la VM prête.",
         f'gcloud compute instances describe {c["name"]} --zone={c["zone"]} '
         f'--format="get(networkInterfaces[0].accessConfigs[0].natIP)"'),
        ("4. Clonage du dépôt sur la VM",
         "Connexion SSH + git clone dans le dossier de travail.",
         f'ssh -i "{c["key_path"]}" -o StrictHostKeyChecking=no {c["ssh_user"]}@<IP_VM> '
         f'"git clone {c["repo"]} {c["work_dir"]}"'),
        ("5. Travail de l'agent (personnalisable)",
         "Emplacement où lancer ton CLI-agent sur la VM (à installer/choisir).",
         f'ssh -i "{c["key_path"]}" {c["ssh_user"]}@<IP_VM> "cd {c["work_dir"]} && <ton agent>"'),
        ("6. Destruction de la VM (nettoyage sécurisé)",
         "Supprime l'instance ET ses disques : aucune trace ne subsiste.",
         f'gcloud compute instances delete {c["name"]} --zone={c["zone"]} '
         f'--delete-disks=all --quiet'),
        ("7. Suppression de la clé SSH locale",
         "Efface la clé éphémère de ta machine (fait en Python via os.remove).",
         f'del "{c["key_path"]}" "{pub}"'),
    ]

def _vps_context(repo):
    name = f'{VPS_CONFIG["name_prefix"]}-{time.strftime("%Y%m%d-%H%M%S")}'
    key_path = os.path.join(tempfile.gettempdir(), name)
    ctx = dict(VPS_CONFIG)
    ctx.update({'name': name, 'repo': repo, 'key_path': key_path})
    return ctx

def print_vps_plan(ctx):
    plan = build_vps_plan(ctx)
    print(f"\n  {C_BOLD}Plan de session — VM « {ctx['name']} »{C_RESET}")
    print(f"  {C_DIM}Repo : {ctx['repo']}{C_RESET}\n")
    for label, note, cmd in plan:
        print(f"  {C_CYAN}{label}{C_RESET}")
        print(f"     {C_DIM}{note}{C_RESET}")
        print(f"     {C_YELLOW}$ {cmd}{C_RESET}\n")
    print(f"  {C_GREEN}💰 Coût estimé{C_RESET} : ~0,01 $ / 2 h sous l'offre gratuite "
          f"(e2-micro Always Free ; seule l'IP externe est facturée).")
    print(f"  {C_GREEN}🔒 Sécurité{C_RESET}   : clé SSH éphémère + destruction VM & disques ; "
          f"pour un repo privé, utilise un token Git à portée limitée que tu révoques après.")

def run_vps_session(scanned):
    """Menu [V] : session VPS éphémère. DRY-RUN par défaut."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\n{C_BLUE}  ┌────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"{C_BLUE}  │        ☁  SESSION VPS ÉPHÉMÈRE (cloud, jetable)        │{C_RESET}")
    print(f"{C_BLUE}  └────────────────────────────────────────────────────────┘{C_RESET}\n")
    print(f"  {C_DIM}Crée une VM GCP jetable → clone le repo → l'agent bosse → détruit la VM.{C_RESET}")
    print(f"  {C_YELLOW}Mode DRY-RUN : rien n'est créé tant que tu n'as pas validé.{C_RESET}\n")

    try:
        repo = input(f"  {C_CYAN}Dépôt Git à travailler [{VPS_CONFIG['default_repo']}] : {C_RESET}").strip()
    except KeyboardInterrupt:
        return
    if not repo:
        repo = VPS_CONFIG['default_repo']

    ctx = _vps_context(repo)
    print_vps_plan(ctx)

    print(f"\n  {C_YELLOW}▲ DRY-RUN : aucune des commandes ci-dessus n'a été exécutée.{C_RESET}")
    print(f"  {C_DIM}Pour lancer réellement (nécessite « gcloud » authentifié), tape "
          f"EXECUTER en majuscules. Entrée = revenir.{C_RESET}")
    try:
        go = input(f"  {C_CYAN}👉 : {C_RESET}").strip()
    except KeyboardInterrupt:
        return
    if go != 'EXECUTER':
        return

    gcloud = find_tool_path('gcloud')
    if not gcloud:
        print(f"\n  {C_RED}⚠ « gcloud » introuvable. Installe le Google Cloud SDK et fais "
              f"« gcloud auth login » avant de réessayer.{C_RESET}")
        time.sleep(3)
        return
    print(f"\n  {C_RED}⚠ EXÉCUTION RÉELLE (expérimentale, non vérifiée contre un vrai projet GCP).{C_RESET}")
    print(f"  {C_DIM}La VM sera systématiquement détruite à la fin, même en cas d'erreur.{C_RESET}")
    try:
        confirm = input(f"  {C_CYAN}Confirmer la création réelle de la VM ? [o/N] : {C_RESET}").strip().lower()
    except KeyboardInterrupt:
        return
    if confirm not in ('o', 'oui', 'y', 'yes'):
        print(f"  {C_YELLOW}Annulé.{C_RESET}")
        time.sleep(1)
        return
    _vps_execute_live(ctx, gcloud)
    try:
        input(f"\n  {C_DIM}Entrée pour revenir au tableau de bord...{C_RESET}")
    except KeyboardInterrupt:
        pass

def _run(argv, **kw):
    return subprocess.run(argv, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', **kw)

def _vps_execute_live(ctx, gcloud):
    """Exécute réellement le cycle de vie. Destruction garantie (finally)."""
    key = ctx['key_path']
    created = False
    try:
        # 1) Clé SSH éphémère
        print(f"\n  {C_CYAN}[1/5] Génération de la clé SSH éphémère...{C_RESET}")
        r = _run(['ssh-keygen', '-t', 'ed25519', '-f', key, '-N', '', '-C', 'ai-ephemeral'])
        if r.returncode != 0:
            print(f"  {C_RED}Échec ssh-keygen : {r.stderr.strip()}{C_RESET}")
            return
        with open(f'{key}.pub', 'r', encoding='utf-8') as f:
            pub = f.read().strip()

        # 2) Création de la VM
        print(f"  {C_CYAN}[2/5] Création de la VM {ctx['name']} (peut prendre ~30 s)...{C_RESET}")
        r = _run([gcloud, 'compute', 'instances', 'create', ctx['name'],
                  f'--zone={ctx["zone"]}', f'--machine-type={ctx["machine_type"]}',
                  f'--image-family={ctx["image_family"]}', f'--image-project={ctx["image_project"]}',
                  f'--metadata=ssh-keys={ctx["ssh_user"]}:{pub}'])
        if r.returncode != 0:
            print(f"  {C_RED}Échec création VM : {r.stderr.strip()[:800]}{C_RESET}")
            return
        created = True

        # 3) IP externe
        print(f"  {C_CYAN}[3/5] Lecture de l'IP externe...{C_RESET}")
        r = _run([gcloud, 'compute', 'instances', 'describe', ctx['name'], f'--zone={ctx["zone"]}',
                  '--format=get(networkInterfaces[0].accessConfigs[0].natIP)'])
        ip = (r.stdout or '').strip()
        if not ip:
            print(f"  {C_RED}IP introuvable : {r.stderr.strip()[:400]}{C_RESET}")
            return
        print(f"     {C_GREEN}IP : {ip}{C_RESET}")

        # 4) Clonage du dépôt (petite attente que SSH soit prêt)
        print(f"  {C_CYAN}[4/5] Clonage du dépôt sur la VM (attente du démarrage SSH)...{C_RESET}")
        time.sleep(20)
        ssh_target = f'{ctx["ssh_user"]}@{ip}'
        r = _run(['ssh', '-i', key, '-o', 'StrictHostKeyChecking=no',
                  '-o', 'UserKnownHostsFile=/dev/null', ssh_target,
                  f'git clone {ctx["repo"]} {ctx["work_dir"]}'])
        print(f"     {C_DIM}{(r.stdout or r.stderr).strip()[:600]}{C_RESET}")

        # 5) Main à l'utilisateur pour travailler dans la VM
        print(f"\n  {C_GREEN}[5/5] VM prête. Connecte-toi pour travailler :{C_RESET}")
        print(f'     {C_YELLOW}ssh -i "{key}" {ssh_target}{C_RESET}')
        print(f"     {C_DIM}(repo cloné dans {ctx['work_dir']}){C_RESET}")
        input(f"\n  {C_CYAN}👉 Appuie sur Entrée quand tu as terminé pour DÉTRUIRE la VM...{C_RESET}")
    except KeyboardInterrupt:
        print(f"\n  {C_YELLOW}Interruption — nettoyage en cours...{C_RESET}")
    except Exception as e:
        print(f"\n  {C_RED}Erreur : {e} — nettoyage en cours...{C_RESET}")
    finally:
        # Destruction garantie de la VM + de la clé locale.
        if created:
            print(f"\n  {C_CYAN}Destruction de la VM {ctx['name']}...{C_RESET}")
            r = _run([gcloud, 'compute', 'instances', 'delete', ctx['name'],
                      f'--zone={ctx["zone"]}', '--delete-disks=all', '--quiet'])
            if r.returncode == 0:
                print(f"  {C_GREEN}✔ VM détruite (instance + disques).{C_RESET}")
            else:
                print(f"  {C_RED}⚠ Échec destruction — vérifie manuellement : "
                      f"gcloud compute instances delete {ctx['name']} --zone={ctx['zone']}{C_RESET}")
        for f in (key, f'{key}.pub'):
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        print(f"  {C_DIM}Clé SSH éphémère supprimée.{C_RESET}")

def main():
    # Définir le titre de la console Windows
    if sys.platform == 'win32':
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("Mes CLI IA - Tableau de Bord")
        except Exception:
            pass
        
    check_and_create_shortcut()
    
    while True:
        # Nettoyer l'écran de manière portable
        os.system('cls' if os.name == 'nt' else 'clear')
        
        scanned = scan_tools()
        print_dashboard(scanned)
        
        print(f"  {C_MAGENTA}{C_BOLD}[A]{C_RESET} 🧠 Demander à l'agent IA (langage naturel — choix auto du CLI)")
        print(f"  {C_BOLD}[M]{C_RESET} ⚙  Choisir le modèle par CLI")
        print(f"  {C_BLUE}{C_BOLD}[V]{C_RESET} ☁  Session VPS éphémère (cloud jetable — dry-run)")
        print(f"  {C_BOLD}[R]{C_RESET} Actualiser la liste")
        print(f"  {C_BOLD}[Q]{C_RESET} Quitter le tableau de bord")
        print()

        try:
            choice = input(f"  {C_CYAN}👉 Votre choix (N°, A, M, V, R ou Q) : {C_RESET}").strip().lower()
        except KeyboardInterrupt:
            print(f"\n\n{C_GREEN}Au revoir !{C_RESET}")
            time.sleep(0.8)
            break
            
        if choice == 'q':
            print(f"\n{C_GREEN}Au revoir !{C_RESET}")
            time.sleep(0.8)
            break
        elif choice == 'a':
            ask_agent(scanned)
            continue
        elif choice == 'm':
            configure_models(scanned)
            continue
        elif choice == 'v':
            run_vps_session(scanned)
            continue
        elif choice == 'r':
            print("\nActualisation...")
            time.sleep(0.5)
            continue
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(scanned):
                selected = scanned[idx]
                if selected['installed']:
                    run_tool(selected)
                else:
                    print(f"\n{C_RED}⚠ L'outil {selected['name']} n'est pas installé.{C_RESET}")
                    time.sleep(2)
            else:
                print(f"\n{C_RED}⚠ Numéro invalide.{C_RESET}")
                time.sleep(1.5)
        except ValueError:
            if choice != '':
                print(f"\n{C_RED}⚠ Option non reconnue.{C_RESET}")
                time.sleep(1.5)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{C_GREEN}Au revoir !{C_RESET}")
        time.sleep(0.8)
