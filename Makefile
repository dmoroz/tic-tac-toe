.PHONY: help env setup run freeze bundle req req-upgrade

PROJECT_NAME=tic-tac-toe
VIRTUALENV_DIR=.env
UNAME=$(shell uname -s)

BS=\033[1m
BE=\033[0m

BSU=\033[1;4m

BLUE=\033[34m
CYAN=\033[36m
GREEN=\033[32m
MAGENT=\033[35m
RED=\033[31m
WHITE=\033[37m
YELLOW=\033[33m

PREFIX=$(BS)=>$(BE)$(WHITE)

ifeq ($(UNAME), Linux)
	ECHO := @echo -e
else
	ECHO := @echo
endif

help:
	$(ECHO) "$(GREEN)$(PREFIX) Follow the next steps to setup $(PROJECT_NAME) project\n\t1. Run $(BSU)make env$(BE) to create virtual environment\n\t2. When your virtual environment is activated, run $(BSU)make setup$(BE)\n\t3. Once setup is ready, run $(BSU)make run$(BE) to start the app."

env:
	$(ECHO) "$(BLUE)$(PREFIX) Creating python virtual environment for $(PROJECT_NAME) project"
	@virtualenv --no-site-packages -q $(VIRTUALENV_DIR)
	$(ECHO) "$(GREEN)$(PREFIX) You can now activate environment using the following command: \n\t1. $(BSU)source $(VIRTUALENV_DIR)/bin/activate$(BE)"

setup: req
	$(ECHO) "$(GREEN)$(PREFIX) Setup is ready"

run:
	$(ECHO) "$(BLUE)$(PREFIX) Running the app"
	@PYTHONPATH=$(PYTHONPATH):. python app.py

freeze:
	$(ECHO) "$(BLUE)$(PREFIX) Creating requirements file"
	@pip freeze > requirements.txt
	$(ECHO) "$(GREEN)$(PREFIX) Requirements file is ready and stored in $(BS)requirements.txt$(BE)"

bundle:
	$(ECHO) "$(BLUE)$(PREFIX) Creating requirements bundle"
	@pip bundle requirements.pybundle -q -r requirements.txt
	$(ECHO) "$(GREEN)$(PREFIX) Bundle is ready and stored in $(BS)requirements.pybundle$(BE)"

req:
	$(ECHO) "$(BLUE)$(PREFIX) Installing requirements"
	@pip install -r requirements.txt

req-upgrade:
	$(ECHO) "$(BLUE)$(PREFIX) Upgrading requirements"
	@pip freeze | cut -d = -f 1 | xargs pip install -U
