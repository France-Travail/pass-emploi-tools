SIMULATION ?= passemploi.test.AccueilFranceTravailSimulation

# Run local des dépendances du parcours accueil FT — connect et api clonés en
# frères de ce repo (convention du projet), surchargeable :
#   make start CONNECT_DIR=… API_DIR=…
CONNECT_DIR ?= ../../pass-emploi-connect
API_DIR ?= ../../pass-emploi-api
RUN_DIR := local-run/.run
HERE := $(CURDIR)

.PHONY: accueilFT loginFT run compile report \
        start stop status logs mock apidb seed connect api marquer-environnement

accueilFT: .env
	. ./.env && ./gradlew gatlingRun --simulation passemploi.test.AccueilFranceTravailSimulation

run: .env
	. ./.env && ./gradlew gatlingRun --simulation $(SIMULATION)

compile:
	./gradlew compileGatlingScala

report:
	xdg-open "$$(ls -td build/reports/gatling/*/ | head -1)index.html"

loginFT: .env
	. ./.env && ./gradlew gatlingRun --simulation passemploi.test.LoginEtAccueilFranceTravailSimulation

.env:
	cp .env.template .env
	@echo ".env créé depuis .env.template : le renseigner puis relancer" && exit 1

# --- Run local (mock-externes + connect + api) — voir local-run/README.md ---

start: mock apidb marquer-environnement seed connect api
	@echo "Lancé — 'make status' pour vérifier, 'make logs' pour suivre, 'make stop' pour arrêter."

# seed/README.md documente ce geste comme "volontairement manuel et absent du
# workflow" — vrai pour le seed réel, qui vise $DATABASE_URL et peut donc
# viser n'importe quel environnement. Ici l'adresse est codée en dur sur
# l'apidb Docker locale (jamais un DATABASE_URL externe) : l'automatiser dans
# `start` n'affaiblit pas le garde-fou anti-prod. Idempotent (INSERT ... WHERE
# NOT EXISTS), donc sans risque à rejouer à chaque `start`.
marquer-environnement:
	psql "postgresql://passemploi:passemploi@localhost:55432/passemploidb" \
	     -f seed/marquer-environnement.sql

mock:
	@mkdir -p $(RUN_DIR)
	@fuser -k 8080/tcp >/dev/null 2>&1 || true
	@cd mock-externes && $(MAKE) install certs
	@cd mock-externes && \
	  ( . pass-emploi-perf-venv/bin/activate && \
	    IDP_ISSUER=https://127.0.0.1:8080/idp \
	    setsid uvicorn app:app --port 8080 --workers 10 \
	      --ssl-keyfile key.pem --ssl-certfile cert.pem \
	      > $(HERE)/$(RUN_DIR)/mock.log 2>&1 & \
	    echo $$! > $(HERE)/$(RUN_DIR)/mock.pid )
	@echo "mock-externes : démarrage (log $(RUN_DIR)/mock.log)"
	@sleep 2

apidb:
	@cd $(API_DIR) && yarn start:pg:db

seed:
	psql "postgresql://passemploi:passemploi@localhost:55432/passemploidb" \
	     -v ON_ERROR_STOP=1 -f seed/seed.sql
	psql "postgresql://passemploi:passemploi@localhost:55432/passemploidb" \
	     -v ON_ERROR_STOP=1 -f seed/verifier.sql

connect:
	@mkdir -p $(RUN_DIR)
	@fuser -k 5050/tcp >/dev/null 2>&1 || true
	@cd $(CONNECT_DIR) && \
	  ( set -a && . $(HERE)/local-run/connect.sh && set +a && \
	    setsid yarn start > $(HERE)/$(RUN_DIR)/connect.log 2>&1 & \
	    echo $$! > $(HERE)/$(RUN_DIR)/connect.pid )
	@echo "connect : démarrage (log $(RUN_DIR)/connect.log)"

api:
	@mkdir -p $(RUN_DIR)
	@fuser -k 5000/tcp >/dev/null 2>&1 || true
	@cd $(API_DIR) && \
	  ( set -a && . $(HERE)/local-run/api.sh && set +a && \
	    setsid yarn start > $(HERE)/$(RUN_DIR)/api.log 2>&1 & \
	    echo $$! > $(HERE)/$(RUN_DIR)/api.pid )
	@echo "api : démarrage (log $(RUN_DIR)/api.log)"

status:
	@for p in mock connect api; do \
	  if [ -f $(RUN_DIR)/$$p.pid ] && kill -0 $$(cat $(RUN_DIR)/$$p.pid) 2>/dev/null; then \
	    echo "$$p : up (pid $$(cat $(RUN_DIR)/$$p.pid))"; \
	  else \
	    echo "$$p : down"; \
	  fi; \
	done

logs:
	tail -n 30 -f $(RUN_DIR)/*.log

stop:
	@for p in mock connect api; do \
	  if [ -f $(RUN_DIR)/$$p.pid ]; then \
	    kill -- -$$(cat $(RUN_DIR)/$$p.pid) 2>/dev/null || true; \
	    rm -f $(RUN_DIR)/$$p.pid; \
	    echo "$$p : arrêté"; \
	  fi; \
	done
	@# uvicorn --workers forke des enfants qui sortent du groupe du process de
	@# tête (multiprocessing) : le kill de groupe ci-dessus ne les touche pas.
	@# fuser cible juste le port 8080, pas pkill -f qui scanne tous les process.
	@fuser -k 8080/tcp >/dev/null 2>&1 || true
