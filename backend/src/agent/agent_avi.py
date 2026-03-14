import csv
import json
import os
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx
from stagehand import AsyncStagehand

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


async def _stream_to_result(stream, label: str) -> object | None:
    """Helper method to process the Stagehand execution stream."""
    result_payload: object | None = None
    async for event in stream:
        if event.type == "log":
            print(f"[{label}][log] {event.data.message}")
            continue

        status = event.data.status
        if status == "finished":
            result_payload = event.data.result
        elif status == "error":
            error_message = event.data.error or "unknown error"
            raise RuntimeError(f"{label} stream reported error: {error_message}")

    return result_payload


async def run_agent_stagehand(
    csv_path: Path,
    session_id: str,
    wait_for_user_submit: Optional[Callable[[int], Awaitable[None]]] = None,
) -> None:
    """
    Exécute l'agent AVI pour remplir le formulaire avec les données du CSV.
    """
    browserbase_api_key = os.environ.get("BROWSERBASE_API_KEY")
    browserbase_project_id = os.environ.get("BROWSERBASE_PROJECT_ID")
    model_api_key = os.environ.get("OPENAI_API_KEY")

    if not browserbase_api_key or not browserbase_project_id:
        raise RuntimeError(
            "BROWSERBASE_API_KEY et BROWSERBASE_PROJECT_ID sont requis dans le .env."
        )
    if not model_api_key:
        raise RuntimeError("OPENAI_API_KEY est requise dans le .env.")

    # Lecture des données CSV
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)

    if not csv_rows:
        raise ValueError("CSV vide")

    # Initialisation du client Stagehand
    async with AsyncStagehand(
        browserbase_api_key=browserbase_api_key,
        browserbase_project_id=browserbase_project_id,
        model_api_key=model_api_key,
    ) as client:
        # Démarrage ou connexion à la session existante via le session_id
        session = await client.sessions.start(
            browserbase_session_id=session_id,
            model_name="openai/gpt-4o",
        )
        print(f"Session Stagehand connectée : {session.id}")

        try:
            for i, row in enumerate(csv_rows):
                print(
                    f"\n--- Traitement de la ligne {i + 1}/{len(csv_rows)} avec Stagehand ---"
                )

                # 1. Navigation vers le formulaire Google
                await session.navigate(url=DEFAULT_LINK)

                # 2. Préparation des instructions strictes pour l'agent
                row_json = json.dumps(row, ensure_ascii=False, indent=2)
                instruction = f"""
                You are an expert web form filler. Your goal is to fill the Google Form using the exact following JSON data.

                DATA FOR THIS SUBMISSION:
                {row_json}

                INSTRUCTIONS:
                1. Match each JSON key to the corresponding form field (text inputs, radio buttons, checkboxes).
                2. If a value contains multiple items separated by commas for a checkbox question, check all corresponding checkboxes.
                3. VERY IMPORTANT: DO NOT click the final "Submit" or "Envoyer" button. Leave the form filled but unsubmitted.
                4. VERIFICATION STEP: Before finishing, review the entire form visually to ensure EVERY piece of data from the JSON has been correctly entered or selected. Correct any missing or incorrect fields.
                5. End your execution successfully ONLY after verifying all fields are accurately filled according to the data.
                """

                # 3. Exécution de l'agent autonome Stagehand
                execute_stream = await session.execute(
                    execute_options={
                        "instruction": instruction,
                        "max_steps": 15,
                    },
                    agent_config={
                        "model": {
                            "model_name": "openai/gpt-4o",
                            "api_key": model_api_key,
                        },
                        "cua": False,
                    },
                    stream_response=True,
                    x_stream_response="true",
                    timeout=300.0,  # Timeout généreux de 5 minutes par ligne
                )

                # Attente la fin du stream et récupérer les résultats
                await _stream_to_result(execute_stream, "execute")
                print(f"--- Agent AVI a terminé de remplir la ligne {i + 1}. ---")

                # 4. Human-in-the-Loop : Pause et attente de la soumission de l'utilisateur
                if wait_for_user_submit is not None:
                    print(
                        "--- En attente de la soumission manuelle de l'utilisateur sur la Live View... ---"
                    )
                    # le code en pause jusqu'a ce qu'on recupere une soumission de l'utilisateur
                    await wait_for_user_submit(i)
                    print(
                        f"--- L'utilisateur a validé la ligne {i + 1}. Passage à la suite. ---"
                    )

        finally:
            # Nettoyage de la session
            await session.end()
            print("Session AVI terminée.")
