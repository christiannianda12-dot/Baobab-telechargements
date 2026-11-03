# Sécurité — état et limites

## En place (testé)
| Mesure | Détail |
|---|---|
| Mots de passe | bcrypt (sel intégré), 10–72 caractères ; temps de réponse égalisé si l'email est inconnu |
| Session navigateur | Cookie `HttpOnly` + `SameSite=Lax` (+ `Secure` automatique en production) : illisible par le JavaScript ; aucun jeton dans `localStorage` (vérifié par test E2E) |
| Clients API / scripts | `Authorization: Bearer` (jeton signé HS256, expiration 60 min par défaut) |
| CSRF | `SameSite=Lax` + contrôle `Origin`/`Referer` sur toute écriture authentifiée par cookie |
| CORS | origines explicites uniquement, credentials autorisés pour elles seules |
| Limitation de débit | connexion/inscription par IP (10/min) ; IP réelle lue dans `X-Forwarded-For` seulement si `TRUST_PROXY_HEADERS=true` |
| En-têtes | API : `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control: no-store`, HSTS + CSP en production. Web : CSP, `nosniff`, `DENY`, HSTS en production |
| Production stricte | refus de démarrer si `SECRET_KEY` < 32 car. ou par défaut, ou si `CORS_ORIGINS` contient `*`/localhost ; documentation Swagger désactivée |
| Validation d'entrées | schémas Pydantic bornés (longueurs, plages, énumérations) ; import CSV borné (2 Mo, 5 000 lignes) |
| Intégrité | contraintes CHECK/UNIQUE/FK ; `predictions` et `prediction_results` append-only par déclencheurs SQL |
| Secrets | uniquement en variables d'environnement ; clés API jamais exposées au frontend ni stockées en base ; `.env` ignoré par git |
| Dépendances | `pip-audit` et `npm audit --omit=dev` : 0 vulnérabilité au 2026-11-03 (relancé en CI) |
| Conteneurs | processus non-root (uid 10001), healthchecks |
| Sauvegardes | `scripts/backup_db.py` (SQLite, rotation, restauration testée), `scripts/backup_pg.sh` (PostgreSQL, rotation) |

## Limites connues (à connaître avant une mise en ligne publique)
1. **Jeton de connexion toujours renvoyé dans le corps de `/auth/login`** (pour les scripts). Le frontend l'ignore, mais un script XSS pourrait appeler l'endpoint. Un mode « cookie seul » est une amélioration possible.
2. **Pas de révocation de jeton** avant expiration (désactiver l'utilisateur bloque l'accès immédiatement, mais un jeton volé d'un compte actif reste valable jusqu'à son expiration). Pas de rafraîchissement : reconnexion toutes les 60 min.
3. **CSP du frontend avec `'unsafe-inline'`** pour les scripts (Next.js injecte des scripts en ligne ; des nonces par requête sont la suite logique).
4. **Limiteur de débit en mémoire** : correct pour une instance ; plusieurs instances exigent un limiteur partagé (Redis) ou celui du reverse proxy. Les écritures hors authentification ne sont pas limitées.
5. **Pas de verrouillage de compte, de vérification d'email, ni de 2FA.**
6. **Règle « pas de prédiction après le coup d'envoi »** appliquée par le service, pas par la base.
7. **Indicateur de session en `localStorage`** (non secret) : un cookie expiré est détecté au premier appel API (401).
8. **Aucun test d'intrusion** n'a été réalisé : les contrôles ci-dessus sont vérifiés par tests automatiques, pas par audit externe.
9. **16 alertes npm « modérées »** sur l'outillage de développement (ESLint/minimatch), hors code déployé.
