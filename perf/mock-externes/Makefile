VENV_DIR = pass-emploi-perf-venv

install:
	python3 -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && pip install --upgrade pip
	. $(VENV_DIR)/bin/activate && pip install -r requirements.txt

install-dev:
	python3 -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && pip install -q --upgrade pip
	. $(VENV_DIR)/bin/activate && pip install -q -r requirements-dev.txt

test: install-dev
	. $(VENV_DIR)/bin/activate && python -m pytest tests -v

# connect impose HTTPS à ses appels IdP : openid-client reçoit un https.Agent
# global (pass-emploi-connect/src/main.ts), qui fait échouer toute cible en
# http:// ("Protocol \"http:\" not supported"). Le mock sert donc en TLS, avec
# un certificat auto-signé — jamais présenté à personne d'autre qu'un
# connect local, qui le prend via NODE_TLS_REJECT_UNAUTHORIZED=0.
certs:
	@test -f cert.pem -a -f key.pem || \
	  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
	    -keyout key.pem -out cert.pem -subj "/CN=localhost" 2>/dev/null
	@echo "cert auto-signé : cert.pem / key.pem"

# IDP_ISSUER doit valoir exactement IDP_FT_JEUNE_ISSUER côté connect, schéma
# compris : sinon openid-client rejette l'id_token ("unexpected iss value").
start: certs
	$(MAKE) install
	. $(VENV_DIR)/bin/activate && \
	  IDP_ISSUER=$${IDP_ISSUER:-https://127.0.0.1:8080/idp} \
	  uvicorn app:app --port 8080 --workers 10 \
	  --ssl-keyfile key.pem --ssl-certfile cert.pem
