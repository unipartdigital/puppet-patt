PYTHON := python3
PIP := pip3

PY_MOD := $(shell grep -v '\#' ${CURDIR}/requirements.txt)

.phony: main depend paramiko puppet-module help

help:
	@echo "before run:"
	@echo " make main"
	@echo ""
	@echo "to create a puppet module archive:"
	@echo " make pgcrt-puppet.tar.xz"
	@echo
	@echo "other target:"
	@echo " make depend"
	@echo " make $(PY_MOD)"

main:
	$(MAKE) depend

$(PY_MOD):
	@echo DEP $@
	${PYTHON} -c "import `echo $@ | tr A-Z a-z`" || ${PIP} install --user $@; \

depend: $(PY_MOD) paramiko

paramiko:
	python3 -c "import paramiko;import sys; paramiko.__version__[:3] >= '2.7' or sys.exit(1)" || ${PIP} install -U --user paramiko

include PUPPET.makefile
