#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
import ctypes
import time

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

# Outils CLI à détecter
CLI_TOOLS = [
    {
        'key': 'agy',
        'name': 'Antigravity CLI',
        'command': 'agy',
        'desc': 'Assistant de code Google DeepMind (Antigravity)'
    },
    {
        'key': 'claude',
        'name': 'Claude Code',
        'command': 'claude',
        'desc': 'Assistant de code Anthropic Claude Code'
    },
    {
        'key': 'opencode',
        'name': 'OpenCode CLI',
        'command': 'opencode',
        'desc': 'Assistant de code OpenCode'
    },
    {
        'key': 'kilocode',
        'name': 'KiloCode CLI',
        'command': 'kilocode',
        'desc': 'Assistant de code KiloCode'
    },
    {
        'key': 'kilo',
        'name': 'Kilo CLI',
        'command': 'kilo',
        'desc': 'Raccourci/Alias de Kilo'
    },
    {
        'key': 'vibe',
        'name': 'Mistral Vibe',
        'command': 'vibe',
        'desc': 'Assistant de code officiel Mistral AI (Vibe)'
    },
    {
        'key': 'mistral',
        'name': 'Mistral CLI',
        'command': 'mistral',
        'desc': 'Interface en ligne de commande Mistral AI'
    }
]

# Dossiers supplémentaires à fouiller si non présents dans le PATH
EXTRA_PATHS = [
    os.path.expandvars(r'%APPDATA%\npm'),
    os.path.expandvars(r'%USERPROFILE%\.local\bin'),
    os.path.expandvars(r'%LOCALAPPDATA%\agy\bin'),
]

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
    for tool in CLI_TOOLS:
        path = find_tool_path(tool['command'])
        version = get_tool_version(path) if path else "N/A"
        scanned.append({
            'name': tool['name'],
            'command': tool['command'],
            'desc': tool['desc'],
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
            print(f"       {C_DIM}↳ {tool['desc']} (Path: {tool['path']}){C_RESET}")
        else:
            print(f"       {C_DIM}↳ {tool['desc']} (Non détecté){C_RESET}")
            
    print(f"\n  {C_DIM}------------------------------------------------------------------------{C_RESET}")
    return installed_count

def run_tool(tool):
    path = tool['path']
    cmd_name = tool['command']
    print(f"\n{C_CYAN}⚡ Lancement de {tool['name']} ({cmd_name})...{C_RESET}")
    print(f"{C_DIM}Dossier de travail actuel : {os.getcwd()}{C_RESET}")
    print(f"{C_DIM}Appuyez sur Ctrl+C ou quittez l'outil pour revenir au tableau de bord.{C_RESET}\n")
    time.sleep(0.5)
    
    try:
        # Exécuter de manière interactive
        if path.lower().endswith(('.cmd', '.bat')):
            subprocess.run([path], shell=True)
        elif path.lower().endswith('.ps1'):
            subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path])
        else:
            subprocess.run([path])
    except KeyboardInterrupt:
        # Capturer l'interruption Ctrl+C si elle se propage à Python
        pass
    except Exception as e:
        print(f"{C_RED}⚠ Erreur lors du lancement de {cmd_name} : {e}{C_RESET}")
        time.sleep(2)
        
    print(f"\n{C_GREEN}✓ Retour au tableau de bord de {tool['name']}.{C_RESET}")
    time.sleep(1.2)

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
        
        print(f"  {C_BOLD}[Q]{C_RESET} Quitter le tableau de bord")
        print(f"  {C_BOLD}[R]{C_RESET} Actualiser la liste")
        print()
        
        try:
            choice = input(f"  {C_CYAN}👉 Votre choix (N° ou Q) : {C_RESET}").strip().lower()
        except KeyboardInterrupt:
            print(f"\n\n{C_GREEN}Au revoir !{C_RESET}")
            time.sleep(0.8)
            break
            
        if choice == 'q':
            print(f"\n{C_GREEN}Au revoir !{C_RESET}")
            time.sleep(0.8)
            break
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
