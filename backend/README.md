# Backend du Projet AgenticAI-Project-F

## Prérequis

Avant de commencer, tu auras besoin de :
- Python 3.10+
- `make` (généralement pré-installé sur Linux et macOS)

## Installation

1.  **Créer et execution l'environnement virtuel**

    Exécute la commande suivante à la racine de ce répertoire (`backend/`) :
    ```sh
    make setup
    ```
    Cette commande va créer un dossier `.venv` à la racine du backend et executer l'environnement virtuel.

2.  **Installer les dépendances**

    Maintenant execute :
    ```sh
    make install
    ```
    Cette commande lit le fichier `requirements.txt` et installe toutes les dépendances listées.

## Lancement du serveur

Pour lancer l'application, utilisez la commande :

```sh
make run
```

Le serveur sera alors accessible à l'adresse suivante : **http://127.0.0.1:8000**
