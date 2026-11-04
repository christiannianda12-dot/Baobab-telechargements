# Utiliser PREDIX AI chez vous, gratuitement (sans serveur)

**Principe** : l'application tourne sur votre ordinateur, dans Docker. Vous l'ouvrez depuis ce PC, et depuis votre téléphone tant qu'il est sur **le même Wi-Fi**. Aucun abonnement, aucun serveur, aucun nom de domaine. Vos données restent sur votre machine.

**Limites à connaître** : l'application n'est disponible que **quand le PC est allumé** et que Docker tourne. Elle n'est pas accessible depuis l'extérieur de votre maison/bureau (c'est voulu : plus sûr).

## 1. Installer Docker Desktop (une seule fois, gratuit pour un usage personnel)
1. Allez sur https://www.docker.com/products/docker-desktop/ et téléchargez la version de votre système.
2. Installez-le (acceptez les options proposées, redémarrez le PC si on vous le demande).
3. Ouvrez **Docker Desktop** une première fois et attendez l'écran principal (la baleine en bas à gauche est verte : « Engine running »).

Prérequis : Windows 10/11 64 bits (ou Mac / Linux), **8 Go de RAM recommandés**, et la virtualisation activée dans le BIOS (c'est le cas par défaut sur la plupart des PC récents ; Docker vous le dira sinon).

## 2. Récupérer l'application
1. Sur GitHub, ouvrez votre dépôt `Baobab-telechargements`, choisissez la branche **`claude/predix-ai-setup-tlx60r`** (menu déroulant en haut à gauche).
2. Bouton vert **« Code »** puis **« Download ZIP »**.
3. Faites un clic droit sur le ZIP → **« Extraire tout… »** dans un dossier simple, par exemple `C:\PREDIX` (évitez un dossier synchronisé OneDrive).

## 3. Démarrer
1. Dans le dossier extrait, **double-cliquez sur `Demarrer-PREDIX.bat`** (Mac/Linux : `./demarrer.sh` dans un terminal).
2. Si Windows affiche « Windows a protégé votre ordinateur », cliquez sur *Informations complémentaires* → *Exécuter quand même* (le fichier est un simple script lisible dans le Bloc-notes).
3. **La première fois, comptez 5 à 15 minutes** (téléchargement et construction). Les fois suivantes : environ 30 secondes.
4. Si Windows demande d'autoriser Docker sur le réseau, acceptez pour les **réseaux privés**.
5. À la fin, le navigateur s'ouvre sur `http://localhost:3000` et la fenêtre affiche l'adresse IP de votre PC.

## 4. Premier compte
Cliquez sur **S'inscrire**. **Le premier compte créé devient administrateur.** Créez-le vous-même, avant de donner l'adresse à quiconque.

## 5. Importer votre historique
1. Récupérez vos fichiers `E0.csv` (les 4 saisons). Ils sont sur la branche `main` de votre dépôt GitHub (téléchargez-les un par un depuis le site), ou retéléchargez-les depuis football-data.co.uk.
2. Dans l'application : **Administration → Import CSV**. Cliquez sur **« Vérifier sans importer »** puis **« Importer »**, un fichier à la fois (commencez par la saison la plus ancienne).
3. Ouvrez la page **Fiabilité** : elle compare le modèle au marché sur votre historique.

## 5 bis. Ajouter d'autres championnats (en un clic)
1. Menu **Centre de données** → onglet **Championnats**.
2. Cliquez sur **Ajouter** à côté d'un championnat (Ligue 1, La Liga, Serie A, Bundesliga, Brésil, USA…), confirmez : l'application télécharge elle-même les 3 dernières saisons (connexion Internet nécessaire).
3. Pour garder les données à jour : **« Tout mettre à jour »** (résultats récents + prochains matchs avec cotes). Une fois par semaine suffit.
4. Après un import, jetez un œil à l'onglet **Qualité** : il liste ce qui mérite vérification. L'onglet **Équipes** propose de fusionner les doublons, et **Historique des imports** permet d'annuler un import erroné.

## 5 ter. Tout automatiser
1. Menu **Paramètres → Automatisation** : laissez « Mise à jour automatique » cochée (toutes les 6 h par défaut) et « Enregistrer automatiquement les prédictions ».
2. Tant que le PC est allumé et Docker ouvert, l'application télécharge seule les résultats, le calendrier et les cotes. La **barre du haut** montre la dernière mise à jour ; « Mettre à jour maintenant » force un cycle.
3. **Coupes européennes** : Centre de données → Championnats → groupe « Coupes européennes (UEFA) » → Ajouter.
4. **Plus de cotes (facultatif)** : créez un compte gratuit sur https://the-odds-api.com, copiez la clé reçue par e-mail dans *Paramètres → Automatisation → Cotes de plus de bookmakers*, « Tester la clé ». L'application ne fait que lire les cotes (quota gratuit limité : environ 500 requêtes par mois).
5. **Combinés** : menu *Combinés → Proposés pour vous*. Lisez toujours la valeur espérée et vérifiez les cotes chez votre bookmaker.
6. Un championnat « refusé » ? Dans *Centre de données*, cliquez sur **Copier le diagnostic** et envoyez-le moi : il contient l'adresse, le code de réponse et la ligne en cause.

## 6. Utiliser depuis le téléphone
1. Le téléphone doit être connecté au **même Wi-Fi** que le PC, qui doit être allumé.
2. Notez l'adresse IPv4 du PC (affichée à la fin du démarrage, par exemple `192.168.1.25`).
3. Sur le téléphone, ouvrez `http://192.168.1.25:3000` (avec **votre** adresse).
4. Dans le navigateur : menu → **« Ajouter à l'écran d'accueil »** pour avoir une icône.

> L'installation complète en tant qu'application (mode hors ligne) exige HTTPS, donc un nom de domaine : ce sera possible plus tard. L'icône d'accueil fonctionne, elle ouvre simplement le site.
> Si la page ne s'ouvre pas : vérifiez le Wi-Fi (certains réseaux « invités » isolent les appareils) et le pare-feu Windows (autoriser Docker sur les réseaux privés).

## 7. Au quotidien
| Je veux… | Je fais… |
|---|---|
| Arrêter | double-clic sur **`Arreter-PREDIX.bat`** (les données sont conservées) |
| Redémarrer | double-clic sur `Demarrer-PREDIX.bat` (Docker Desktop doit être ouvert) |
| **Sauvegarder mes données** | double-clic sur **`Sauvegarder-PREDIX.bat`** → copie dans le dossier `sauvegardes`. **Copiez-le aussi sur une clé USB** : si le PC tombe en panne, tout part avec. Faites-le après chaque gros import. |
| Mettre à jour l'application | retéléchargez le ZIP (branche à jour), extrayez-le **par-dessus** l'ancien dossier (gardez `.env.local`), puis relancez `Demarrer-PREDIX.bat`. Les données sont dans un volume Docker, elles ne sont pas effacées. |
| Supprimer toutes les données | `docker compose -f docker-compose.local.yml down -v` (**irréversible**, après sauvegarde) |

## 8. Sécurité à la maison
- Toute personne branchée sur votre Wi-Fi peut atteindre la page de connexion : choisissez un **mot de passe solide** (10 caractères minimum) et ne laissez pas d'inconnus sur votre réseau.
- N'utilisez **pas** ce mode sur un Wi-Fi public (café, hôtel).
- Ne partagez jamais le fichier `.env.local` (il contient la clé secrète de votre instance).

## 9. Plus tard, si vous voulez l'ouvrir à l'extérieur (facultatif)
Il faudra un accès HTTPS depuis Internet : soit un petit serveur (voir `docs/SERVEUR.md`), soit un service de tunnel gratuit comme *Cloudflare Tunnel* (à vérifier avant usage : conditions, nom de domaine requis). Ce n'est pas nécessaire pour l'usage interne.

## 10. Rappel important sur les résultats
La page **Fiabilité** montre que le modèle est **moins précis que les bookmakers** sur l'historique testé. Utilisez la plateforme pour analyser et comparer, **pas pour parier de l'argent sur ses seuls signaux**.
