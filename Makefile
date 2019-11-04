
CYTHON3 := $(shell which cython3 2> /dev/null || which cython3.8 2> /dev/null || which cython3.6 2> /dev/null)

main: ip_takeover

ip_takeover.c: ip_takeover.py
	$(CYTHON3) -3 --embed ip_takeover.py

ip_takeover: ip_takeover.c
	gcc `python3-config --cflags --ldflags` -o ip_takeover ip_takeover.c
	strip --strip-unneeded ip_takeover

install: ip_takeover
	install -o root -g postgres -m 4750 ip_takeover /usr/local/sbin/

clean:
	$(RM) ip_takeover.c

distclean: clean
	$(RM) ip_takeover
