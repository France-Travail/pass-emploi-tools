SIMULATION ?= passemploi.test.AccueilFranceTravailSimulation

# Run local des dépendances du parcours accueil FT — connect et api clonés en
# frères de ce repo (convention du projet), surchargeable :
#   make start CONNECT_DIR=… API_DIR=…
CONNECT_DIR ?= ../../pass-emploi-connect
API_DIR ?= ../../pass-emploi-api
RUN_DIR := local-run/.run
HERE := $(CURDIR)

.PHONY: accueilFT loginFT run compile report \
        start stop status logs mock apidb seed connect api marquer-environnement \
        firebase-fake tir

accueilFT: .env
	. ./.env && ./gradlew gatlingRun --simulation passemploi.test.AccueilFranceTravailSimulation

run: .env
	. ./.env && ./gradlew gatlingRun --simulation $(SIMULATION)

compile:
	./gradlew compileGatlingScala

# Servi en HTTP plutôt qu'ouvert en file:// : un navigateur en bac à sable
# (Flatpak, snap) reçoit le fichier via le portail de documents, qui n'expose
# que l'index.html demandé — sans ses répertoires style/ et js/, d'où un
# rapport sans CSS ni graphiques.
REPORT_PORT ?= 8123

report:
	@dir="$$(ls -td build/reports/gatling/*/ | head -1)"; \
	  echo "Rapport servi sur http://localhost:$(REPORT_PORT)/ (Ctrl-C pour arrêter)"; \
	  xdg-open "http://localhost:$(REPORT_PORT)/" >/dev/null 2>&1 & \
	  python3 -m http.server $(REPORT_PORT) --directory "$$dir" --bind 127.0.0.1

loginFT: .env
	. ./.env && ./gradlew gatlingRun --simulation passemploi.test.LoginEtAccueilFranceTravailSimulation

# --- Tir sur Scalingo (gatling-perf) — voir README.md, § Tirer depuis Scalingo ---

GATLING_APP ?= gatling-perf
SCALINGO_REGION ?= osc-secnum-fr1
MAX_USERS ?= 20
RAMP_DURATION_IN_SECONDS ?= 60
HOLD_DURATION_IN_SECONDS ?= 120
# Simulation par défaut différente de celle de `run` : AccueilFranceTravailSimulation
# attend un JWT fourni à la main, inutilisable en tir sans intervention — tandis
# que LoginEtAccueilFranceTravailSimulation se logue elle-même via connect-perf.
TIR_SIMULATION ?= passemploi.test.LoginEtAccueilFranceTravailSimulation

# --size XL : un injecteur sous-dimensionné devient le facteur limitant du
# tir, et on mesurerait l'injecteur plutôt que l'application (même logique
# que le choix Scalingo plutôt qu'un runner GitHub partagé).
# --no-daemon : le daemon Gradle n'a aucun intérêt dans un conteneur
# one-off jetable — il accélère les builds *suivants*, qu'il n'y aura pas.
# --console=plain -q : la barre de progression ANSI de Gradle est illisible
# une fois relayée par `scalingo run` ; -q coupe le bruit de cycle de vie
# de Gradle sans toucher à la sortie du process forké (résumé Gatling).
tir:
	scalingo --region $(SCALINGO_REGION) --app $(GATLING_APP) run --size XL \
	  --env MAX_USERS=$(MAX_USERS) \
	  --env RAMP_DURATION_IN_SECONDS=$(RAMP_DURATION_IN_SECONDS) \
	  --env HOLD_DURATION_IN_SECONDS=$(HOLD_DURATION_IN_SECONDS) \
	  "./gradlew --no-daemon --console=plain -q gatlingRun --simulation $(TIR_SIMULATION)"

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
	@cd mock-externes && $(MAKE) install
	@cd mock-externes && \
	  ( . pass-emploi-perf-venv/bin/activate && \
	    setsid uvicorn app:app --port 8080 --workers 10 \
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

# Credentials Firebase factices : l'API se connecte sinon au vrai projet
# pass-emploi-staging avec les clés du .environment. Générés plutôt que
# committés — une clé privée en dur dans git, même bidon, fait sonner les
# scanners de secrets.
firebase-fake:
	@mkdir -p $(RUN_DIR)
	@test -f $(RUN_DIR)/firebase-fake.json || { \
	  openssl genrsa 2048 2>/dev/null > $(RUN_DIR)/firebase-fake.key && \
	  python3 -c "import json,sys; k=open('$(RUN_DIR)/firebase-fake.key').read(); \
	    json.dump({'type':'service_account','project_id':'pass-emploi-local-fake', \
	    'private_key_id':'fake','private_key':k, \
	    'client_email':'fake@pass-emploi-local-fake.iam.gserviceaccount.com', \
	    'client_id':'000000000000000000000','auth_uri':'https://accounts.google.com/o/oauth2/auth', \
	    'token_uri':'https://oauth2.googleapis.com/token'}, open('$(RUN_DIR)/firebase-fake.json','w'))" && \
	  rm -f $(RUN_DIR)/firebase-fake.key && \
	  echo "credentials Firebase factices générés"; }

api: firebase-fake
	@mkdir -p $(RUN_DIR)
	@fuser -k 5000/tcp >/dev/null 2>&1 || true
	@cd $(API_DIR) && \
	  ( set -a && LOCAL_RUN_DIR=$(HERE)/local-run . $(HERE)/local-run/api.sh && set +a && \
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
