#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cria a estrutura de pastas do Bot TikTok.
Execute este script na pasta onde o bot ficará instalado.
"""

import os
from pathlib import Path

# ── Configuração ──────────────────────────────
# Altere aqui quantos nichos e contas deseja criar
NICHOS    = ["Nicho 1", "Nicho 2"]
NUM_CONTAS = 5
# ─────────────────────────────────────────────

BASE = Path(__file__).parent

print("=" * 50)
print("  Setup — Bot TikTok Auto Poster")
print("=" * 50)
print(f"\nPasta base: {BASE}\n")

for nicho in NICHOS:
    nicho_dir = BASE / nicho
    nicho_dir.mkdir(exist_ok=True)
    (nicho_dir / "postados").mkdir(exist_ok=True)
    print(f"[OK] {nicho}/")
    print(f"[OK] {nicho}/postados/")
    for i in range(1, NUM_CONTAS + 1):
        (nicho_dir / f"conta{i}").mkdir(exist_ok=True)
        print(f"[OK] {nicho}/conta{i}/")
    print()

print("=" * 50)
print("  Estrutura criada com sucesso!")
print("=" * 50)
print("""
Próximos passos:
  1. Dentro de cada pasta  NichoX\\contaN\\  coloque:
       - O atalho .lnk do Opera (já logado no TikTok)
       - Os vídeos .mp4 para postar

  2. Execute: iniciar.bat  para abrir o bot

  3. No app: selecione o nicho, configure as descrições
     e clique em INICIAR POSTAGEM
""")

input("Pressione Enter para fechar...")
