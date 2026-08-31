import os
import uvicorn
from fastapi import FastAPI

app = FastAPI()

API_SIMULATOR_URL = os.getenv("API_SIMULATOR_URL", "http://127.0.0.1:8080")


##################################################
##
##  OPENID (mock du Keycloak pass-emploi)
##
##  Le workflow accueil FT y passe 3 fois :
##  1. discovery  : l'API découvre jwks_uri au 1er appel (puis cache)
##  2. certs      : clés publiques servant à valider le JWT du jeune
##  3. token      : token exchange JWT jeune -> token IDP France Travail
##
##################################################

@app.get("/issuer/.well-known/openid-configuration")
async def openid_config():
    return {
        "authorization_endpoint"     : f"{API_SIMULATOR_URL}/auth/realms/pass-emploi/protocol/openid-connect/auth",
        "claims_parameter_supported" : False,
        "claims_supported"           : [
            "sub",
            "email",
            "userId",
            "userRoles",
            "userStructure",
            "userType",
            "family_name",
            "given_name",
            "preferred_username",
            "sid",
            "auth_time",
            "iss"
        ],
        "code_challenge_methods_supported" : ["S256","plain"],
        "end_session_endpoint"             : f"{API_SIMULATOR_URL}/auth/realms/pass-emploi/protocol/openid-connect/logout",
        "grant_types_supported"            : [
            "implicit",
            "authorization_code",
            "refresh_token",
            "urn:ietf:params:oauth:grant-type:token-exchange"
        ],
        "issuer"    : f"{API_SIMULATOR_URL}/auth/realms/pass-emploi",
        "jwks_uri"  : f"{API_SIMULATOR_URL}/auth/realms/pass-emploi/protocol/openid-connect/certs",
        "authorization_response_iss_parameter_supported" : True,
        "response_modes_supported"                       : [
            "form_post",
            "fragment",
            "query"
        ],
        "response_types_supported" : [
            "code id_token",
            "code",
            "id_token",
            "none"
        ],
        "scopes_supported" : [
            "openid",
            "offline_access",
            "email",
            "profile"
        ],
        "subject_types_supported" : ["public"],
        "token_endpoint_auth_methods_supported" : [
            "client_secret_basic",
            "client_secret_jwt",
            "client_secret_post",
            "private_key_jwt",
            "none"
        ],
        "token_endpoint_auth_signing_alg_values_supported" : ["HS256","RS256","PS256","ES256","EdDSA"],
        "token_endpoint" : f"{API_SIMULATOR_URL}/auth/realms/pass-emploi/protocol/openid-connect/token",
        "id_token_signing_alg_values_supported" : ["PS256","RS256"],
        "pushed_authorization_request_endpoint" : f"{API_SIMULATOR_URL}/auth/realms/pass-emploi/protocol/openid-connect/ext/par/request",
        "request_parameter_supported" : False,
        "request_uri_parameter_supported" : False,
        "userinfo_endpoint" : f"{API_SIMULATOR_URL}/auth/realms/pass-emploi/protocol/openid-connect/userinfo",
        "claim_types_supported":["normal"]
    }


# Clés publiques du Keycloak de STAGING (id.pass-emploi.incubateur.net) :
# seul un JWT émis par ce Keycloak passe la validation de signature côté API.
# Pour tirer avec des JWT d'un autre environnement, remplacer par les clés du
# Keycloak cible : GET {keycloak}/auth/realms/pass-emploi/protocol/openid-connect/certs
@app.get("/auth/realms/pass-emploi/protocol/openid-connect/certs")
async def openid_certs_staging():
    return {"keys":[{
        "kty":"RSA",
        "use":"sig",
        "kid":"8xLSMPDVXLfdcfuwR2Gaib-m67KXh0t7sXuTe16zZ-0",
        "e":"AQAB",
        "n":"6BGtvONO4jUwmfXP2kkNuyLhvY8WP4z-Onll4pnZmEHHVaMC9LbP52pDTN2HQWEA9wd6kWxDkdaDTo3QA4fTZoi39iLNtUpbVDYIX3NwDUk5EuaUOKfCtMwwAYh6K3sYQCPV6O7kwkBOMD8EYOZYqllpNcVvAAFCo1PRxt5p9FLSFSZqlTsQ2E0zi-3Rr68lKVvunXmRZKXGeHsjC9M-0-Gn9dAXJXmsbT6X2AbOMr4U_O73XSfKzpHcweCSKeJnRyVyt0k0Mto6ILtlPVRj7ujBYfesLfZhWp_BJpk5Roov458WLEGWIAH7d0puYrr228rPrtC_inJCpiEssMyC4Q"
    },{
        "kty":"RSA",
        "use":"sig",
        "kid":"UFcQqDxYxd2GuzhzqpQjXkqFZLMCzjeM1qVtp7DV43c",
        "e":"AQAB",
        "n":"lAcQZKng6AUEfR80Kq1-dH1v1kTH3i8nVX-8jtZ1L6wGT_E8N5Q1KyYF5Q3JNP-mL8h8YxmOEZr41xwCrExBIZET1BPLfGbEDBBvAvWCC8vC2IFkOmkTI_wiGlyb5zPnLP8jW5YzZVsmKjhto5BiobbkuY2pvvFGC3sXDcJIS_bkdtx6Ot-NuNEIYLBOuNO5MFDAF8QhBBEtZAMrGvKrSHW-QYltv-tJBwXL_JaiEpjYHnEwmdVVfr9axYwMaZ89Y-x0MaHIRBS59antWyfVqlFqD9S5jfIeJfGZ30eUOj9xe4jwjYvUjXEq5UWi2o_eRMDcnNPG4ycWaqXHw5rTDQ"
    }]}


# Token exchange : la valeur retournée n'a aucune importance, les APIs FT
# qui la consomment sont mockées ci-dessous
@app.post("/issuer/protocol/openid-connect/token")
async def openid_token():
    return {
        "issued_token_type" : "urn:ietf:params:oauth:token-type:access_token",
        "access_token"      : "fake-idp-token",
        "token_type"        : "bearer",
        "expires_in"        : 1139,
        "scope"             : "individu demarches openid profile prestationDE api_peconnect-demarchesv1 api_peconnect-gerer-prestationsv1 api_peconnect-rendezvousagendav2 email demarchesW"
    }


##################################################
##
##  FRANCE TRAVAIL (les 3 APIs appelées par l'accueil)
##
##################################################

@app.get("/poleemploi/peconnect-demarches/v1/demarches")
async def poleemploi_peconnect_demarches():
    return [{
        "code": 'P02',
        "libelle": 'Ma formation professionnelle',
        "typesDemarcheRetourEmploi": [
          {
            "type": 'TypeDemarcheRetourEmploiReferentielPartenaire',
            "code": 'Q06',
            "libelle": "Information sur un projet de formation ou de Validation des acquis de l'expérience",
            "moyensRetourEmploi": [
              {
                "type": 'MoyenRetourEmploiReferentielPartenaire',
                "code": 'C06.01',
                "libelle": "En participant à un atelier, une prestation, une réunion d'information",
                "droitCreation": False
              }
            ]
          }
        ]
      }
    ]

""" params = dateRecherche=2025-02-10 """
@app.get("/poleemploi/peconnect-gerer-prestations/v1/rendez-vous")
async def poleemploi_peconnect_rdv():
    return []

""" params = ?dateDebut=2025-02-10T13%3A43%3A37.941Z """
@app.get("/poleemploi/peconnect-rendezvousagenda/v2/listerendezvous")
async def poleemploi_peconnect_listerdv():
    return []


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        access_log=False
    )
