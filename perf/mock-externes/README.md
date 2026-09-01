# API Simulator

Mock des dépendances externes de pass-emploi-api, réduit au strict nécessaire
du workflow **accueil jeune France Travail**
(`GET /jeunes/{idJeune}/pole-emploi/accueil`) :

| Route mockée | Rôle dans le workflow |
|---|---|
| `GET /issuer/.well-known/openid-configuration` | Discovery OIDC (l'API y découvre `jwks_uri`, 1 fois puis cache) |
| `GET /auth/realms/pass-emploi/protocol/openid-connect/certs` | Clés publiques pour valider le JWT du jeune |
| `POST /issuer/protocol/openid-connect/token` | Token exchange JWT jeune → token IDP France Travail |
| `GET /poleemploi/peconnect-demarches/v1/demarches` | Démarches du jeune (1 démarche factice) |
| `GET /poleemploi/peconnect-gerer-prestations/v1/rendez-vous` | Prestations (vide) |
| `GET /poleemploi/peconnect-rendezvousagenda/v2/listerendezvous` | Rendez-vous agenda (vide) |

## Lancer le simulateur

```sh
make start          # venv + deps + uvicorn sur :8080
```

`API_SIMULATOR_URL` doit contenir l'URL à laquelle **pass-emploi-api** joint le
simulateur (elle est injectée dans les URLs du discovery) :

```sh
API_SIMULATOR_URL="http://127.0.0.1:8080"
```

## Brancher pass-emploi-api dessus

Deux variables suffisent pour le workflow accueil (`.environment` de l'API) :

```sh
OIDC_ISSUER_URL=http://127.0.0.1:8080/issuer
POLE_EMPLOI_API_BASE_URL=http://127.0.0.1:8080/poleemploi
```

## Contrainte sur le JWT

Le simulateur sert les clés publiques du Keycloak de **staging**
(`id.pass-emploi.incubateur.net`) : le `USER_TOKEN` du tir Gatling doit donc
être un vrai JWT émis par ce Keycloak (ex. via le Swagger de l'API staging),
**non expiré** (durée de vie courte : en regénérer un avant chaque tir),
appartenant au jeune ciblé. Pour tirer avec un JWT d'un autre environnement,
remplacer les clés dans `app.py` par celles du Keycloak cible
(`GET {keycloak}/auth/realms/pass-emploi/protocol/openid-connect/certs`).
Symptôme d'un mauvais appariement clé/JWT : 100 % de 401 dès le guard d'authent.
