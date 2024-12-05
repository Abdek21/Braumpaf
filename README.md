# Bot Discord Multifonction

Un bot Discord polyvalent avec des fonctionnalités de modération, des commandes interactives et des fonctionnalités automatisées.

## Installation

1. Clonez ce dépôt
2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Créez une application Discord sur [Discord Developer Portal](https://discord.com/developers/applications)
4. Copiez le token du bot
5. Modifiez le fichier `.env` et remplacez `votre_token_ici` par votre token
6. Invitez le bot sur votre serveur en utilisant le lien d'invitation généré dans le portail développeur

## Fonctionnalités

### Commandes de base
- `!ping` - Vérifie si le bot répond
- `!help` - Affiche la liste des commandes disponibles

### Commandes interactives
- `!dice [faces]` - Lance un dé (nombre de faces optionnel)
- `!say <message>` - Fait répéter un message par le bot

### Commandes de modération
- `!clear <nombre>` - Supprime un nombre spécifié de messages
- `!kick <@membre> [raison]` - Expulse un membre avec une raison optionnelle

### Fonctionnalités automatiques
- Message de bienvenue pour les nouveaux membres
- Message d'au revoir pour les membres qui partent

### Fonctionnalités avancées
- `!joke` - Affiche une blague aléatoire

## Configuration requise

- Python 3.8 ou supérieur
- Les permissions nécessaires sur Discord pour les commandes de modération

## Permissions Discord nécessaires

Le bot nécessite les permissions suivantes :
- Lire et envoyer des messages
- Gérer les messages
- Expulser des membres
- Voir les membres du serveur
- Lire l'historique des messages
