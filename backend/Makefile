setup: ## créer l'environnement virtuel.
    python3 -m venv .venv
    source .venv/bin/activate

install:  ## Installe les dependances .
	pip install -r requirements.txt

run: ## lance le serveur.
	uvicorn src.api.main:app --reload
