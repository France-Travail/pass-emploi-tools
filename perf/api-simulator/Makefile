VENV_DIR = pass-emploi-perf-venv

install:
	python3 -m venv $(VENV_DIR)
	. $(VENV_DIR)/bin/activate && pip install --upgrade pip
	. $(VENV_DIR)/bin/activate && pip install -r requirements.txt

start:
	$(MAKE) install
	. $(VENV_DIR)/bin/activate && uvicorn app:app --port 8080 --workers 10
