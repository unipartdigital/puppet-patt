
. PHONY: test

test:root.key root.pem srv.key srv.pem
	./self_signed_certificate.py yaml -f test_self_signed_certificate.yaml --verify

root.key root.pem srv.key srv.pem:
	./self_signed_certificate.py yaml -f test_self_signed_certificate.yaml

clean:
	$(RM) root.key root.pem srv.key srv.pem
