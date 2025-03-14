# 🎓 Automatisation de l'émargement v2.4

Ce projet vise à automatiser l'émargement des étudiants de l'Université Bretagne Sud, en particulier ceux de l'ENSIBS. En utilisant Selenium dans un conteneur Docker, il enregistre automatiquement leur présence en cours, évitant ainsi toute retenue sur leur salaire. Son fonctionnement : chaque jour de la semaine, il récupère les cours de l'étudiant via l'API de PlanningSup et, au début de chaque cours, il émarge automatiquement entre 15 et 25 minutes après le début du cours.

> [!CAUTION]
> Ce dépôt Github est à utiliser avec prudence. Si vous le mettez en place, assurez-vous d'être présent à chaque cours de votre emploi du temps.

## 📌 Installation

1. Clonez le dépôt Github

   ```bash
   git clone https://github.com/MTlyx/Emarge.git && cd Emarge
   ```

2. Modifiez les variables d'environnement dans `docker-compose.yml`

   Les variables à modifier sont les suivantes :
   - `FORMATION` : Formation de l'étudiant (`cyberdefense`, `cyberdata` ou `cyberlog`)
   - `ANNEE` : Année d'étude (`3`, `4` ou `5`)
   - `TP` : Numéro du groupe de TP (`1` à `6`)
   - `BLACKLIST` : Liste de mots-clés pour exclure certains cours de l'émargement automatique
   - `LANG` : Définir sur `EN` si Moddle est en anglais, `FR` sinon (valeur par défaut)

   Exemple de configuration d'un cyberdefense en 3eme année dans le TP 1 :
   ```yaml
   - FORMATION=cyberdefense
   - ANNEE=3
   - TP=1
   - BLACKLIST=Entrainement Le Robert, Activités HACK2G2, Activités GCC
   ```

   > [!NOTE]
   > La `blacklist` est une liste de mots-clés permettant d'exclure certains cours de l'émargement automatique. Lors de l'exécution, tout cours dont le nom contient un des mots-clés de la `blacklist` ne sera pas émargé. Il est recommandé de laisser la blacklist comme dans l'exemple ci-dessus.

3. Modifiez les variables d'environnement dans `secrets.env`

   Les variables à modifier sont les suivantes :
   - `USERNAME` : Votre identifiant UBS
   - `PASSWORD` : Votre mot de passe UBS
   - `TOPIC` : Le *topic* que vous avez choisi d'utiliser pour les notifications (laissez vide si vous ne voulez pas utiliser cette fonctionnalité)

   Exemple de configuration :
   ```yaml
   USERNAME=e123456
   PASSWORD=MonSuperMotDePasse
   TOPIC=UnTrucRandom
   ```

4. Lancez le conteneur Docker

   ```bash
   sudo docker compose up -d
   ```

## Upgrade

Pour commencer, il faut supprimer le conteneur Docker avec la commande

```bash
sudo docker compose down
```

Ensuite, il faut mettre à jour le projet avec conteneur Docker, commencez par mettre à jour les différents fichiers avec

```bash
git pull
```

Enfin, il ne reste plus qu'à le relancer avec l'option `--build` en plus

```bash
sudo docker compose up --build -d
```

## Notifications

Les notifications sont gérées avec [ntfy.sh](https://ntfy.sh/). C'est très simple d'utilisation :

1. Installez l'application [ntfy.sh](https://ntfy.sh/) (stores officiels, F-Droid ou [source](https://github.com/binwiederhier/ntfy))

   ![ntfy.sh](https://raw.githubusercontent.com/binwiederhier/ntfy/refs/heads/main/.github/images/screenshot-phone-main.jpg)

2. Appuyez sur le `+` en bas a droite et entrez un *topic*. Cela correspond à une adresse à laquelle vous allez vous "abonner", et l'application utilisera cette adresse pour envoyer des notifications.

   > [!NOTE]
   > Ces *topics* sont publics, entrez donc une valeur aléatoire pour éviter de recevoir des notifications envoyées par d'autres personnes.

3. Entrer le *topic* que vous avez utilisé dans le fichier `secrets.env`, et relancez le Docker.


## 📊 Vérification des logs

Vous pouvez vérifier vos logs de deux manières :

1. Directement depuis Docker :

   ```bash
   sudo docker compose logs -f
   ```

2. En consultant le fichier de log :

   ```bash
   cat app/emargement.log
   ```

Les logs vous permettront de voir :
- Les horaires prévus d'émargement
- Les succès/échecs des émargements
- Les éventuelles erreurs
