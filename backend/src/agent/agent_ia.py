from browser_use import (
    Agent,
    Browser,
    BrowserProfile,
    ChatGoogle,
    ChatOpenAI,
    ChatGroq,
    ChatVercel,
)

import asyncio
import csv
import json
from pathlib import Path
from typing import Callable, Optional

DEFAULT_LINK = "https://forms.gle/4m4xQ1PgtB8GtCj66"


# async def run_agent(csv_path: Path, row_index: int = 0) -> None:
#     llm = ChatGroq(model="moonshotai/kimi-k2-instruct-0905")

#     browser = Browser(
#         headless=False,  # Show browser window
#         window_size={"width": 1000, "height": 700},  # Set window size
#     )

#     with csv_path.open("r", encoding="utf-8", newline="") as f:
#         reader = csv.DictReader(f)
#         csv_rows = list(reader)

#     if not csv_rows:
#         raise ValueError("CSV vide")
#     if row_index < 0 or row_index >= len(csv_rows):
#         raise IndexError(
#             f"row_index hors limites: {row_index} (lignes={len(csv_rows)})"
#         )

#     row_json = json.dumps(csv_rows[row_index], ensure_ascii=False, indent=2)

#     prompt = f"""
#         Tu es un expert en remplissage automatique de formulaires web à partir de données utilisateur. Ton objectif est de remplir et soumettre un formulaire en ligne de manière fiable, en minimisant les erreurs.

#         Contexte et ressources :
#         - L’URL du formulaire à ouvrir est : {DEFAULT_LINK}
#         - Le fichier CSV a été reçu via l’API et est stocké ici : {csv_path}

#         Données à utiliser (JSON pour UNE soumission, ligne {row_index}):
#         {row_json}

#         Mission :
#         1) Ouvre le lien : {DEFAULT_LINK}
#         2) Associe chaque clé/valeur JSON au champ correspondant du formulaire (en te basant sur les libellés, placeholders, ou tout indice visible).
#         3) Remplis le formulaire avec ces valeurs.
#         4) Vérifie les champs obligatoires et les formats.
#         5) Soumets le formulaire.
#         6) Si l’envoi est confirmé, réponds uniquement : "C'est bon". Sinon, explique l’erreur.

#         Contraintes importantes :
#         - Ne pas inventer de données.
#         - Si une donnée obligatoire manque, indique précisément laquelle.
#     """

#     agent = Agent(
#         task=prompt,
#         browser=browser,
#         llm=llm,
#     )

#     await agent.run()


async def run_agent(
    csv_path: Path,
    on_row_done: Optional[Callable[[int, bool, str | None], None]] = None,
) -> dict:
    llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct")

    browser_profile = BrowserProfile(
        headless=True,
        window_size={"width": 1000, "height": 700},
    )

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)

    if not csv_rows:
        raise ValueError("CSV vide")

    submitted = 0
    failed = 0
    errors: list[dict] = []

    for i, row in enumerate(csv_rows):
        row_json = json.dumps(row, ensure_ascii=False, indent=2)
        task = f"""
            Tu es un expert en remplissage automatique de formulaires web à partir de données utilisateur. Ton objectif est de remplir et soumettre un formulaire en ligne de manière fiable, en minimisant les erreurs.

            Contexte et ressources :
            - L’URL du formulaire à ouvrir est : {DEFAULT_LINK}
            - Le fichier CSV a été reçu via l’API et est stocké ici : {csv_path}

            Données à utiliser (JSON pour UNE soumission, ligne {i}):
            {row_json}

            Mission :
            1) Ouvre le lien : {DEFAULT_LINK}
            2) Associe chaque clé/valeur JSON au champ correspondant du formulaire (en te basant sur les libellés, placeholders, ou tout indice visible).
            3) Remplis le formulaire avec ces valeurs.
            4) Vérifie les champs obligatoires et les formats.
            5) Soumets le formulaire.
            6) Si Google Forms affiche des erreurs (cadres rouges, message "Cette question est obligatoire", champs invalides, etc.), alors :
               - Repère toutes les questions en erreur.
               - Reviens sur ces questions (scroll si nécessaire) et complète-les à partir des données JSON.
               - Pour les questions à cases à cocher/multi-sélection : si la valeur JSON contient des virgules, considère que ce sont plusieurs choix et coche chaque option correspondante.
               - Pour les réponses multiples (radio/select) : choisis l’option la plus exactement identique au texte dans le formulaire.
               - Retente l’envoi.
               - Répète ce cycle jusqu’à réussite, avec une limite de 3 tentatives d’envoi maximum.
            7) Si l’envoi est confirmé, réponds uniquement : "C'est bon". Sinon, explique précisément les champs qui bloquent et pourquoi (question obligatoire non trouvée, valeur inexistante dans le formulaire, etc.).
        """

        agent = Agent(task=task, browser_profile=browser_profile, llm=llm)
        try:
            await agent.run()
            submitted += 1
            if on_row_done is not None:
                on_row_done(i, True, None)
        except Exception as e:
            failed += 1
            err = str(e)
            errors.append({"row_index": i, "error": err})
            if on_row_done is not None:
                on_row_done(i, False, err)

    return {
        "total": len(csv_rows),
        "submitted": submitted,
        "failed": failed,
        "errors": errors,
    }
