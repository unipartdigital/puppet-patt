
PYTHON=/usr/bin/env python3

HAVE_PARAMIKO = $(shell $(PYTHON) -c "import paramiko"; echo $$?)

paramiko:
ifneq ($(HAVE_PARAMIKO),0)
	pip3 install -U --user paramiko
endif
