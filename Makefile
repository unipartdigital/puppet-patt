PYTHON := python3

PY_MOD := $(shell grep -v '\#' ${CURDIR}/requirements.txt)

.phony: main depend paramiko puppet-module help

help:

	@echo "to create a puppet module archive:"
	@echo " make patt-puppet.tar.xz"
	@echo
	@echo "to create a puppet module branch:"
	@echo " make patt-puppet"
	@echo
	@echo "other target:"
	@echo " make depend"
	@echo

$(PY_MOD):
	@echo DEP $@
ifeq ($@, paramiko)
	python3 -c "import paramiko;import sys; paramiko.__version__[:3] >= str('2.7') or sys.exit(1)" || \
${PYTHON} -m pip install -U --user paramiko
else
	${PYTHON} -c "import `echo $@ | tr A-Z a-z`" || ${PYTHON} -m pip install --user $@;
endif

depend: $(PY_MOD) paramiko

-include PUPPET.makefile

patt-puppet: patt-puppet.tar.xz
	git checkout puppet || git checkout -b puppet && \
find ./* ! -ipath "./patt-puppet.tar.xz" -delete && \
tar xvf patt-puppet.tar.xz --strip-components=2 && \
rm -f patt-puppet.tar.xz && \
git add . && git commit -m "`date +%s`" || true

clean:
	find . -type f -name "*~" -delete
	find . -type f -name "*.pyc" -delete
