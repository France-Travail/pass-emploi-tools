import base64
import hashlib
import json
import os
import random
import tempfile
import time
from urllib.parse import quote

import jwt
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Header, Request
from fastapi.responses import RedirectResponse

app = FastAPI()

# Doit valoir exactement IDP_FT_JEUNE_ISSUER côté connect : openid-client
# compare l'iss de l'id_token à l'issuer configuré et rejette sinon.
IDP_ISSUER = os.getenv("IDP_ISSUER", "http://127.0.0.1:8080/idp")

# Convention partagée avec le seed : le sub rendu ici doit correspondre à
# l'id_authentification d'un jeune semé, sinon l'API refuse le login
# (aucune auto-création, cf. update-utilisateur.command.handler.ts).
POOL_SIZE = int(os.getenv("POOL_SIZE", "50"))
POOL_PREFIX = os.getenv("POOL_PREFIX", "perf-ft-")

CHEMIN_CLE = os.getenv(
    "IDP_CLE_PRIVEE_PEM",
    os.path.join(tempfile.gettempdir(), "mock-externes-idp.pem"),
)


def _charger_ou_creer_cle(chemin: str) -> rsa.RSAPrivateKey:
    # Les workers uvicorn sont des process distincts qui importent chacun ce
    # module : une clé générée à l'import serait différente par worker, et le
    # /jwks servi par l'un ne validerait pas l'id_token signé par l'autre —
    # connect rejette alors en RPError "no valid key found in issuer's
    # jwks_uri", et seule la fraction 1/workers des logins aboutit.
    #
    # La clé transite donc par un fichier, écrit par le premier worker qui y
    # arrive. Le os.link est atomique et échoue si la cible existe : un seul
    # gagnant, et les perdants relisent son fichier plutôt que le leur.
    if not os.path.exists(chemin):
        provisoire = f"{chemin}.{os.getpid()}"
        nouvelle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        descripteur = os.open(provisoire, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descripteur, "wb") as fichier:
            fichier.write(
                nouvelle.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
        try:
            os.link(provisoire, chemin)
        except FileExistsError:
            pass
        finally:
            os.unlink(provisoire)

    with open(chemin, "rb") as fichier:
        return serialization.load_pem_private_key(fichier.read(), password=None)


_CLE_PRIVEE = _charger_ou_creer_cle(CHEMIN_CLE)


def _entier_en_b64(valeur: int) -> str:
    octets = valeur.to_bytes((valeur.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(octets).decode().rstrip("=")


_NOMBRES_PUBLICS = _CLE_PRIVEE.public_key().public_numbers()
_KID = hashlib.sha256(str(_NOMBRES_PUBLICS.n).encode()).hexdigest()[:16]
_JWK = {
    "kty": "RSA",
    "use": "sig",
    "alg": "RS256",
    "kid": _KID,
    "n": _entier_en_b64(_NOMBRES_PUBLICS.n),
    "e": _entier_en_b64(_NOMBRES_PUBLICS.e),
}


def _encoder(charge: dict) -> str:
    brut = json.dumps(charge, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(brut).decode().rstrip("=")


def _decoder(jeton: str) -> dict:
    padding = "=" * (-len(jeton) % 4)
    return json.loads(base64.urlsafe_b64decode(jeton + padding))


def identite_du_pool() -> str:
    return f"{POOL_PREFIX}{random.randrange(POOL_SIZE)}"


def _sub_du_porteur(entete_authorization: str) -> str:
    jeton = entete_authorization.removeprefix("Bearer ").strip()
    if not jeton:
        return identite_du_pool()
    return _decoder(jeton)["sub"]


##################################################
##
##  IDP FRANCE TRAVAIL
##
##  connect ne fait aucun discovery : il construit son client à partir des
##  quatre URLs ci-dessous, fournies par variables d'environnement.
##
##  Sans état de session : l'identité tirée au /auth est encodée dans le code,
##  que le /token décode. Rien à synchroniser entre les workers pendant un tir
##  (la clé de signature, elle, leur est commune : cf. _charger_ou_creer_cle).
##
##################################################


@app.get("/idp/protocol/openid-connect/certs")
async def idp_certs():
    return {"keys": [_JWK]}


@app.get("/idp/protocol/openid-connect/auth")
async def idp_authorize(redirect_uri: str, state: str = "", nonce: str = ""):
    code = _encoder({"sub": identite_du_pool(), "nonce": nonce})
    separateur = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        f"{redirect_uri}{separateur}code={code}&state={quote(state)}",
        status_code=302,
    )


@app.post("/idp/protocol/openid-connect/token")
async def idp_token(request: Request):
    formulaire = await request.form()
    client_id = formulaire.get("client_id", "")
    jeton = formulaire.get("code") or formulaire.get("refresh_token") or ""

    contexte = _decoder(jeton) if jeton else {"sub": identite_du_pool(), "nonce": ""}
    sub = contexte["sub"]
    maintenant = int(time.time())

    id_token = jwt.encode(
        {
            "iss": IDP_ISSUER,
            "sub": sub,
            "aud": client_id,
            "exp": maintenant + 3600,
            "iat": maintenant,
            "auth_time": maintenant,
            "nonce": contexte.get("nonce", ""),
            "preferred_username": sub,
        },
        _CLE_PRIVEE,
        algorithm="RS256",
        headers={"kid": _KID},
    )

    # L'access_token porte le même encodage que le code : c'est ce qui permet
    # au userinfo et aux APIs partenaires de retrouver l'identité du porteur.
    jeton_acces = _encoder({"sub": sub, "nonce": contexte.get("nonce", "")})

    return {
        "access_token": jeton_acces,
        "id_token": id_token,
        "refresh_token": jeton_acces,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "openid profile email",
    }


@app.get("/idp/protocol/openid-connect/userinfo")
async def idp_userinfo(authorization: str = Header(default="")):
    sub = _sub_du_porteur(authorization)
    return {"sub": sub, "preferred_username": sub}


##################################################
##
##  APIS PARTENAIRES FRANCE TRAVAIL
##
##  Appelées par connect pendant le login (coordonnees, statut) et par l'api
##  pendant l'accueil (demarches, prestations, agenda).
##
##################################################


# Pour un bénéficiaire FT Connect, connect prend nom/prénom/email ICI et non
# dans le userinfo (idp.service.ts, getCoordonnees). Les dériver du sub : un
# nom constant masquerait un mauvais appariement d'identité.
@app.get("/poleemploi/peconnect-coordonnees/v1/coordonnees")
async def poleemploi_coordonnees(authorization: str = Header(default="")):
    sub = _sub_du_porteur(authorization)
    return {"nom": "Perf", "prenom": sub, "email": f"{sub}@perf.local"}


# Filet : connect n'appelle cette route que si l'API a répondu
# UTILISATEUR_INEXISTANT. Avec un jeune correctement semé, elle reste morte.
@app.get("/poleemploi/peconnect-statut/v1/statut")
async def poleemploi_statut():
    return {"codeStatutIndividu": "1"}


@app.get("/poleemploi/peconnect-demarches/v1/demarches")
async def poleemploi_demarches():
    return [
        {
            "code": "P02",
            "libelle": "Ma formation professionnelle",
            "typesDemarcheRetourEmploi": [
                {
                    "type": "TypeDemarcheRetourEmploiReferentielPartenaire",
                    "code": "Q06",
                    "libelle": "Information sur un projet de formation ou de Validation des acquis de l'expérience",
                    "moyensRetourEmploi": [
                        {
                            "type": "MoyenRetourEmploiReferentielPartenaire",
                            "code": "C06.01",
                            "libelle": "En participant à un atelier, une prestation, une réunion d'information",
                            "droitCreation": False,
                        }
                    ],
                }
            ],
        }
    ]


@app.get("/poleemploi/peconnect-gerer-prestations/v1/rendez-vous")
async def poleemploi_prestations():
    return []


@app.get("/poleemploi/peconnect-rendezvousagenda/v2/listerendezvous")
async def poleemploi_agenda():
    return []


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, access_log=False)
