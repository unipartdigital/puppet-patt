
CYTHON3 := $(shell which cython3 2> /dev/null || which cython-3.9 2> /dev/null || which cython-3.8 2> /dev/null || which cython-3.6 2> /dev/null)
PYTHON := python3

DESTDIR ?=
PREFIX ?= /usr/local

.PHONY: scapy scapy_root install uninstall clean distclean

main: ip_takeover

scapy:
# install from pip if no system module
	-$(shell $(PYTHON) -c "import scapy" || $(PYTHON) -m pip install --user scapy[basic])

scapy_root:
	-$(shell sudo $(PYTHON) -c "import scapy" || sudo $(PYTHON) -m pip install --pre scapy[basic])

ip_takeover.py: scapy

ip_takeover.c: ip_takeover.py
	$(CYTHON3) -3 --embed ip_takeover.py

ip_takeover: ip_takeover.c
	gcc -fPIC -o ip_takeover ip_takeover.c `{ python3-config --embed > /dev/null && python3-config --cflags --ldflags --embed ; } || python3-config --cflags --ldflags`
	strip --strip-unneeded ip_takeover

$(DESTDIR)$(PREFIX)/sbin/ip_takeover: ip_takeover scapy_root
	sudo install -o root -g postgres -m 4750 ip_takeover $(DESTDIR)$(PREFIX)/sbin/
$(DESTDIR)$(PREFIX)/src/ip_takeover/:
	sudo mkdir -p $(DESTDIR)$(PREFIX)/src/ip_takeover/
$(DESTDIR)$(PREFIX)/src/ip_takeover/ip_takeover.make: $(DESTDIR)$(PREFIX)/src/ip_takeover/
	sudo install -o root -g root -m 644 ip_takeover.make $(DESTDIR)$(PREFIX)/src/ip_takeover/
$(DESTDIR)$(PREFIX)/src/ip_takeover/ip_takeover.py: $(DESTDIR)$(PREFIX)/src/ip_takeover/
	sudo install -o root -g root -m 644 ip_takeover.py $(DESTDIR)$(PREFIX)/src/ip_takeover/

install: $(DESTDIR)$(PREFIX)/src/ip_takeover/ip_takeover.make $(DESTDIR)$(PREFIX)/src/ip_takeover/ip_takeover.py $(DESTDIR)$(PREFIX)/sbin/ip_takeover

uninstall:
	sudo $(RM) $(DESTDIR)$(PREFIX)/sbin/ip_takeover         ; \
sudo $(RM) $(DESTDIR)$(PREFIX)/src/ip_takeover/ip_takeover.py   ; \
sudo $(RM) $(DESTDIR)$(PREFIX)/src/ip_takeover/ip_takeover.make ; \
sudo rmdir $(DESTDIR)$(PREFIX)/src/ip_takeover/

clean:
	$(RM) ip_takeover.c

distclean: clean
	$(RM) ip_takeover
