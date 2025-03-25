# 🎓 Automatisation de l'émargement v2.4

Ce projet vise à automatiser l'émargement des étudiants de l'Université Bretagne Sud, en particulier ceux de l'ENSIBS. En utilisant Selenium dans un conteneur Docker, il enregistre automatiquement leur présence en cours, évitant ainsi toute retenue sur leur salaire. Son fonctionnement : chaque jour de la semaine, il récupère les cours de l'étudiant via l'API de PlanningSup et vérifie s'il y a une mise à jour. Au début de chaque cours, il émarge automatiquement entre 5 et 10 minutes après le début du cours. De plus, il est possible de recevoir une notification sur son téléphone pour être informé des nouvelles mises à jour, des émargements réussis ainsi que des possibles erreurs.

> [!CAUTION]
> Ce dépôt Github est à utiliser avec prudence. Si vous le mettez en place, assurez-vous d'être présent à chaque cours de votre emploi du temps.

## 📌 Installation

1. Clonez le dépôt Github

```bash
git clone https://github.com/MTlyx/Emarge.git && cd Emarge
```

2. Modifiez les variables d'environnement du fichier `docker-compose.yml`

Les variables à modifier sont les suivantes :
- `FORMATION` : formation de l'étudiant (cyberdefense, cyberdata ou cyberlog)
- `ANNEE` : Année d'étude (3, 4 ou 5)
- `TP` : Numéro du groupe de TP (1 à 6)
- `Us` : Votre identifiant UBS
- `Pa` : Votre mot de passe UBS
- `blacklist` : Liste de mots-clés pour exclure certains cours de l'émargement
- `TOPIC` : Votre topic nfty à configurer ici [📢 Notification](#📢%20Notification)

Exemple de configuration d'un cyberdefense en 3eme année dans le TP 1
```yaml
- FORMATION=cyberdefense
- ANNEE=3
- TP=1
- Us=E123456
- Pa=MonSuperMotDePasse
- blacklist=Entrainement Le Robert, Activités HACK2G2, Activités GCC, Séminaire Facteur Humain
- TOPIC=XXXXXXXXXXX
- MODE=EMARGEMENT
```

> [!NOTE]
> La `blacklist` est une liste de mots-clés permettant d'exclure certains cours de l'émargement automatique. Lors de l'exécution, tout cours dont le nom contient un des mots-clés de la `blacklist` ne sera pas émargé. Il est recommandé de laisser la blacklist comme dans l'exemple ci-dessus.

3. Lancez le conteneur Docker

```bash
sudo docker compose up -d
```

## 📢 Notification

Les notifications sont gérées avec [ntfy.sh](https://ntfy.sh/), son utilisation est très simple

1. Télécharger l'application sur Google Play ou l'App Store

2. Configurez les notifications en appuyant sur le **+** puis en sélectionner un **topic**, il faudra aussi le rajouter dans le ``docker-compose.yml``

3. Au premier lancement du programme d'émargement, vous devriez recevoir une notification pour tester la bonne configuration de ntfy

Il est aussi possible de passer le programme en mode notification seulement et il n'émargera pas à votre place

1. Mettre la directive de build ``target`` à ``notification`` dans  le ``docker-compose.yml``

2. Bien renseigner le **topic** dans le ``docker-compose.yml``

3. L'utilisation de ``Us`` et ``Pa`` est inutile vous pouvez les retirer.

4. Avant de relancer l'app avec ``docker compose up -d`` il faut la rebuild avec ``docker compose build``

> [!NOTE]
> Les **topics** sont partagés et hébergés sur un serveur public, entrez donc une valeur aléatoire pour éviter de recevoir des notifications indésirables envoyées par d'autres utilisateurs ainsi que de partager vos notifications

Merci à [@Eudaeon](https://github.com/Eudaeon) pour l'idée ainsi que de l'intégration

## Upgrade

Pour commencer, il faut supprimer le conteneur Docker avec la commande

```bash
sudo docker compose down
```

Ensuite, il faut mettre à jour le projet avec conteneur Docker, commencez par mettre à jour les différents fichiers avec

```bash
git reset --hard
git pull
```

Enfin, il ne reste plus qu'à le relancer avec l'option `--build` en plus

```bash
sudo docker compose up --build -d
```

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
