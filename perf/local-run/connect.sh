# Surcharge de pass-emploi-connect/.environment pour un run 100% local contre
# mock-externes — NE MODIFIE PAS le .environment chiffré, ne fait que
# l'écraser via process.env (`ConfigModule` charge le fichier en premier).
#
# Aucun secret ici : tout vient des docker-compose.yml déjà versionnés des
# deux repos, ou de mock-externes lui-même. Rien à saisir, rien à vaulter.
#
# Usage, depuis pass-emploi-connect/ :
#   set -a && source ../pass-emploi-tools/perf/local-run/connect.sh && set +a
#   yarn start

# Conteneur redis de connect ("cej-auth-redis") — résout "redis" en interne au
# réseau docker compose de connect, injoignable par un `yarn start` natif :
# on retombe sur le port publié. Mot de passe = REDIS_PASSWORD du
# docker-compose.yml de connect.
export REDIS_URL="redis://:myredispassword@localhost:6777/0"

# IdP France Travail -> mock-externes (perf/mock-externes, make start, :8080)
export IDP_FT_JEUNE_ISSUER="http://127.0.0.1:8080/idp"
export IDP_FT_JEUNE_AUTHORIZATION_URL="http://127.0.0.1:8080/idp/protocol/openid-connect/auth"
export IDP_FT_JEUNE_TOKEN_URL="http://127.0.0.1:8080/idp/protocol/openid-connect/token"
export IDP_FT_JEUNE_JWKS="http://127.0.0.1:8080/idp/protocol/openid-connect/certs"
export IDP_FT_JEUNE_USERINFO="http://127.0.0.1:8080/idp/protocol/openid-connect/userinfo"
# Le mock ne vérifie ni client_id ni client_secret : les valeurs du
# .environment conviennent, pas besoin de les surcharger.

# CRITIQUE : sans cette surcharge, le mock redirige avec la vraie valeur du
# .environment (https://id.pass-emploi.incubateur.net/...) — un run "local"
# tape alors un vrai domaine externe. Doit valoir le connect local.
export IDP_FT_JEUNE_REDIRECT_URI="http://localhost:5050/auth/realms/pass-emploi/broker/pe-jeune/endpoint"

# Vide = pas de realm : idp.service.ts n'ajoute le paramètre que si truthy.
export IDP_FT_JEUNE_REALM=""

# API partenaire France Travail -> mock-externes
export FT_JEUNE_API_URL="http://127.0.0.1:8080/poleemploi"

# pass-emploi-api en local (voir api.sh)
export PASS_EMPLOI_API_URL="http://localhost:5000"

# La route PUT /auth/users de l'API est gardée par API_KEY_KEYCLOAK
# (authentification.controller.ts, partenaire KEYCLOAK). En local, l'API porte
# les clés factices de son .environment ; connect doit présenter la même,
# sinon 401 et login en échec UTILISATEUR_NON_TRAITABLE.
export PASS_EMPLOI_API_KEY="ceci-est-une-api-key"

export PORT="5050"

# CRITIQUE : sans cette surcharge, oidc-provider construit ses redirections
# (interaction, reprise, …) sur le vrai domaine du .environment
# (https://id.pass-emploi.incubateur.net/...) — un run "local" repart taper
# l'extérieur en pleine chaîne de login.
export PUBLIC_ADDRESS="http://localhost:5050/auth/realms/pass-emploi"
