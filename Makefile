PYTHON := python3
PIP := pip3

PY_MOD := $(shell grep -v '\#' ${CURDIR}/requirements.txt)

.phony: depend

main:
	$(MAKE) depend

$(PY_MOD):
	@echo DEP $@
	${PYTHON} -c "import `echo $@ | tr A-Z a-z`" || ${PIP} install --user $@; \

depend: $(PY_MOD)
