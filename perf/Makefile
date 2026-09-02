SIMULATION ?= passemploi.test.AccueilFranceTravailSimulation

.PHONY: accueilFT loginFT run compile report

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
