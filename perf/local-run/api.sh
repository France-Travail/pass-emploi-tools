# Surcharge de pass-emploi-api/.environment pour un run 100% local contre
# mock-externes + connect local — NE MODIFIE PAS le .environment chiffré, ne
# fait que l'écraser via process.env (`ConfigModule` charge le fichier en
# premier).
#
# Aucun secret ici : tout vient des docker-compose.yml déjà versionnés des
# deux repos, ou de mock-externes lui-même. Rien à saisir, rien à vaulter.
#
# Usage, depuis pass-emploi-api/ :
#   yarn start:pg:db   # apidb (postgis, :55432) + migrations
#   set -a && source ../pass-emploi-tools/perf/local-run/api.sh && set +a
#   yarn start
export PORT="5000"

# .environment vaut "staging" -> providers.ts force le SSL Sequelize, que
# l'apidb locale ne sait pas parler ("server does not support SSL
# connections"). Le seed/garde-fou local n'a pas besoin de ce SSL.
export ENVIRONMENT="local"

# apidb du docker-compose de l'api (postgis/postgis:14-3.2-alpine, :55432)
export DATABASE_URL="postgresql://passemploi:passemploi@localhost:55432/passemploidb"

# Émetteur du JWT : le connect local (voir connect.sh, PORT=5050), jamais
# mock-externes lui-même — c'est connect qui signe. Chemin d'issuer complet,
# pas la base nue : l'API fait un Issuer.discover dessus
# (/.well-known/openid-configuration), et c'est aussi la valeur du claim iss.
export OIDC_ISSUER_URL="http://localhost:5050/auth/realms/pass-emploi"

# APIs partenaires France Travail -> mock-externes (perf/mock-externes, :8080)
export POLE_EMPLOI_API_BASE_URL="https://127.0.0.1:8080/poleemploi"
