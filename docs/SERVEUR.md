# Acquérir un serveur et mettre PREDIX AI en ligne — guide pas à pas

Ce guide part de zéro. Compter **1 à 2 heures** la première fois. Les prix sont **indicatifs** (à vérifier sur les sites avant de payer).

## 1. Ce qu'il faut acheter

| Élément | Choix conseillé | Ordre de grandeur |
|---|---|---|
| **Serveur (VPS)** | 2 vCPU, **4 Go de RAM**, 40 Go SSD, Linux **Ubuntu 24.04 LTS** | 4 à 8 € / mois |
| **Nom de domaine** | un `.com`, `.net`, `.app`… | 10 à 15 € / an |

Fournisseurs de VPS courants (aucun n'est imposé, l'application fonctionne chez tous) :
- **Hetzner Cloud** : très bon rapport qualité/prix, datacenters en Europe.
- **OVHcloud (VPS)** : fournisseur européen, interface en français.
- **Scaleway**, **DigitalOcean**, **Contabo** : alternatives.

Domaine : OVHcloud, Gandi, Namecheap, Cloudflare Registrar.

**Pourquoi 4 Go de RAM** : la construction du site (Next.js) et la base de données PostgreSQL consomment de la mémoire ; avec 1–2 Go, la mise en ligne risque d'échouer.

> Un VPS est **un serveur loué** : vous n'avez rien à brancher chez vous. Vous vous y connectez par Internet avec un terminal.

## 2. Créer le serveur
1. Créez un compte chez le fournisseur choisi (une pièce d'identité peut être demandée).
2. Créez un serveur : **image Ubuntu 24.04**, offre 2 vCPU / 4 Go, un datacenter proche de vos utilisateurs.
3. Notez son **adresse IP** (quatre nombres, ex. `203.0.113.10`).
4. **Accès** : choisissez une **clé SSH** si le fournisseur le propose (plus sûr). Sous Windows 10/11, ouvrez PowerShell et tapez `ssh-keygen` (Entrée à chaque question) ; la clé publique est dans `C:\Users\VOTRE_NOM\.ssh\id_ed25519.pub` : copiez son contenu dans le formulaire. Sinon, le fournisseur vous envoie un mot de passe `root`.

## 3. Relier le domaine au serveur
Dans l'interface de votre registraire de domaine, section **DNS** : ajoutez un enregistrement
- Type **A** · Nom **@** (ou le sous-domaine voulu, ex. `predix`) · Valeur **l'IP du serveur**.

La propagation prend de 5 minutes à quelques heures. Test : `ping votre-domaine.com` doit afficher l'IP du serveur.

## 4. Se connecter et préparer le serveur
Dans PowerShell (Windows) ou le Terminal (Mac) :
```bash
ssh root@IP_DU_SERVEUR
```
Puis, une fois connecté :
```bash
apt update && apt -y upgrade
# Pare-feu : seuls SSH, HTTP et HTTPS sont ouverts
ufw allow OpenSSH && ufw allow 80 && ufw allow 443/tcp && ufw allow 443/udp && ufw --force enable
# Docker (méthode officielle)
curl -fsSL https://get.docker.com | sh
```

## 5. Récupérer l'application
Le dépôt GitHub est privé : créez d'abord un **jeton d'accès** (GitHub → Settings → Developer settings → Personal access tokens → *Fine-grained* → accès **lecture seule** au dépôt `Baobab-telechargements`, permission « Contents : Read »). Ensuite :
```bash
git clone https://github.com/christiannianda12-dot/Baobab-telechargements.git predix
# identifiant : christiannianda12-dot   mot de passe : (collez le jeton)
cd predix && git checkout claude/predix-ai-setup-tlx60r
```

## 6. Configurer
```bash
cp .env.example .env
echo "DOMAIN=votre-domaine.com" >> .env
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)" >> .env
echo "SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')" >> .env
```
Les trois lignes ajoutées à la fin l'emportent sur les valeurs d'exemple (quand une variable apparaît deux fois, la dernière compte). Vérification : `grep -E "^(DOMAIN|POSTGRES_PASSWORD|SECRET_KEY)=" .env` doit afficher vos trois valeurs en dernier. Gardez ce fichier **secret** et faites-en une copie sauvegardée hors du serveur : sans lui, impossible de relancer la base.

## 7. Lancer
```bash
./scripts/deploy.sh
```
Le script construit les images, démarre tout et attend la santé de l'API (5 à 10 minutes la première fois). Caddy obtient le certificat HTTPS tout seul (le DNS doit déjà pointer vers le serveur). Ouvrez `https://votre-domaine.com`.

**Créez tout de suite votre compte** : le premier compte devient administrateur.

## 8. Importer votre historique
Vos fichiers ont été déposés sur la branche `main` du dépôt. Sur le serveur :
```bash
git fetch origin main && mkdir -p imports
for i in 1 2 3 4; do git show "origin/main:E0 ($i).csv" > "imports/e0_$i.csv"; done
docker compose -f docker-compose.prod.yml exec api python -m app.cli.import_csv /imports/e0_4.csv /imports/e0_3.csv /imports/e0_2.csv /imports/e0_1.csv --dry-run
docker compose -f docker-compose.prod.yml exec api python -m app.cli.import_csv /imports/e0_4.csv /imports/e0_3.csv /imports/e0_2.csv /imports/e0_1.csv
```
(Le dossier `imports/` est monté en lecture seule dans le conteneur.) Puis ouvrez la page **Fiabilité** de l'application.

## 9. Sauvegardes (important)
- Une sauvegarde PostgreSQL est faite **chaque jour** dans `predix/backups/` (14 jours conservés).
- Elles sont sur **le même serveur** : si le serveur disparaît, elles aussi. Copiez-les régulièrement ailleurs (depuis votre PC : `scp root@IP:~/predix/backups/*.dump .`) et activez les **instantanés (snapshots)** payants de votre fournisseur si possible.
- Testez de temps en temps une restauration (voir `docs/DEPLOYMENT.md`).

## 10. Mises à jour
```bash
cd predix && git pull && ./scripts/deploy.sh
```

## 11. Installer l'application sur le téléphone
Ouvrez `https://votre-domaine.com` dans Chrome (Android) ou Safari (iPhone), puis **« Ajouter à l'écran d'accueil »** (Android : menu ⋮ → *Installer l'application*). L'icône apparaît comme une application.

## 12. À savoir avant d'ouvrir au public
- **Vous êtes responsable** des données et de l'usage : limitez l'inscription à vos proches tant que vous n'avez pas relu `docs/SECURITY.md` (pas de 2FA, pas de vérification d'email).
- **Cadre légal** : l'analyse sportive et les paris sont réglementés selon les pays (âge minimum, publicité, licences). Renseignez-vous avant toute ouverture publique ou commerciale.
- **Honnêteté du produit** : la page Fiabilité montre que le modèle est moins précis que les bookmakers. Ne présentez jamais ses probabilités comme des certitudes ou des conseils de pari.

## En cas de problème
| Symptôme | Piste |
|---|---|
| Le site affiche une erreur de certificat | Le DNS ne pointe pas encore vers le serveur, ou les ports 80/443 sont fermés (`ufw status`). Attendez et relancez `./scripts/deploy.sh`. |
| `deploy.sh` s'arrête sur « manquant dans .env » | Une variable manque ou vaut encore `change-me`. |
| L'API ne répond pas | `docker compose -f docker-compose.prod.yml logs api` |
| Construction qui échoue faute de mémoire | Serveur trop petit (< 4 Go) : changez d'offre ou ajoutez du swap. |
