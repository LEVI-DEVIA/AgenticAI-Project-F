import csv
import json
import os
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx
from browser_use import (
    Agent,
    BrowserProfile,
    ChatGroq,
    ChatOpenAI,
)
from browser_use.browser.session import BrowserSession

DEFAULT_LINK = "https://forms.gle/4m4xQ1PgtB8GtCj66"


async def create_browserbase_session() -> dict:
    api_key = os.getenv("BROWSERBASE_API_KEY")
    if not api_key:
        raise RuntimeError("BROWSERBASE_API_KEY manquant")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://api.browserbase.com/v1/sessions",
            headers={
                "X-BB-API-Key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "keepAlive": True,
                "timeout": 3600,
                "browserSettings": {
                    "viewport": {"width": 1200, "height": 800},
                },
            },
        )

    if res.status_code != 201:
        raise RuntimeError(
            f"Browserbase session create failed: {res.status_code} {res.text}"
        )

    return res.json()


async def get_browserbase_live_view_urls(session_id: str) -> dict:
    api_key = os.getenv("BROWSERBASE_API_KEY")
    if not api_key:
        raise RuntimeError("BROWSERBASE_API_KEY manquant")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"https://api.browserbase.com/v1/sessions/{session_id}/debug",
            headers={
                "X-BB-API-Key": api_key,
            },
        )

    if res.status_code != 200:
        raise RuntimeError(
            f"Browserbase debug urls failed: {res.status_code} {res.text}"
        )

    return res.json()


async def run_agent(
    csv_path: Path,
    cdp_url: str | None = None,
    wait_for_user_submit: Optional[Callable[[int], Awaitable[None]]] = None,
) -> None:
    # llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct")
    llm = ChatOpenAI(
        model="o3",
    )
    browser_profile = BrowserProfile(
        headless=True,
        # window_size={"width": 1200, "height": 800},
        # chrome_instance_path=None,
        cdp_url=cdp_url,
        keep_alive=True,
    )

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)

    if not csv_rows:
        raise ValueError("CSV vide")

    if not cdp_url:
        raise RuntimeError("cdp_url manquant")

    browser_session = BrowserSession(
        cdp_url=cdp_url,
        browser_profile=browser_profile,
        keep_alive=True,
    )

    try:
        await browser_session.start()

        for i, row in enumerate(csv_rows):
            row_json = json.dumps(row, ensure_ascii=False, indent=2)
            task = f"""
                Tu es un expert en remplissage automatique de formulaires web à partir de données utilisateur. Ton objectif est de remplir un formulaire en ligne de manière fiable, en minimisant les erreurs.

                Contexte et ressources :
                - L’URL du formulaire à ouvrir est : {DEFAULT_LINK}
                - Le fichier CSV a été reçu via l’API et est stocké ici : {csv_path}

                Données à utiliser (JSON pour UNE soumission, ligne {i}):
                {row_json}

                Mission :
                1) Ouvre le lien : {DEFAULT_LINK}
                1bis) Si tu vois une page confirmant une soumission déjà faite (ex: texte "Your response has been recorded" / "Votre réponse a été enregistrée"), alors :
                   - Clique sur "Submit another response" / "Envoyer une autre réponse" si disponible,
                   - Sinon, rouvre l’URL : {DEFAULT_LINK}
                2) Associe chaque clé/valeur JSON au champ correspondant du formulaire (en te basant sur les libellés, placeholders, ou tout indice visible).
                3) Remplis le formulaire avec ces valeurs.
                4) Vérifie les champs obligatoires et les formats.
                5) IMPORTANT : Ne clique PAS sur le bouton "Envoyer" / "Submit". Laisse l'utilisateur le faire.
                6) Si Google Forms affiche des erreurs (cadres rouges, message "Cette question est obligatoire", champs invalides, etc.), alors :
                   - Repère toutes les questions en erreur.
                   - Reviens sur ces questions (scroll si nécessaire) et complète-les à partir des données JSON.
                   - Pour les questions à cases à cocher/multi-sélection : si la valeur JSON contient des virgules, considère que ce sont plusieurs choix et coche chaque option correspondante.
                   - Pour les réponses multiples (radio/select) : choisis l’option la plus exactement identique au texte dans le formulaire.
                   - N'essaie pas de soumettre.
                7) Quand tout est prêt et qu'il ne reste plus qu'à cliquer sur "Envoyer" / "Submit", réponds uniquement : "READY".
                8) TRÈS IMPORTANT : Si tu vois visuellement que les champs sont déjà remplis avec tes données, ou si tu obtiens des erreurs "Element not available" plus de 2 fois en essayant de remplir la fin du formulaire, NE RECOMMENCE PAS en boucle. Considère que c'est terminé et réponds "READY".
            """

            agent = Agent(
                task=task,
                browser_session=browser_session,
                llm=llm,
                step_timeout=600,
                use_judge=False,
                generate_gif=False,
                # max_actions_per_step=3,
            )
            await agent.run()

            if wait_for_user_submit is not None:
                await wait_for_user_submit(i)
    finally:
        await browser_session.stop()
