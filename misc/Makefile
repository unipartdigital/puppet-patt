
CA_PASS := secret123
ifneq ($(CA_PASS),)
CA_PASS_OPT := --ca_key_pass_phrase "$(CA_PASS)"
CA_PASS_OPT_OPENSSL := -passin pass:$(CA_PASS)
endif

. PHONY: yaml_test cli_test

main: yaml_test cli_test

yaml_test:
	@echo "--------"
	@echo $@
	@echo "--------"
	$(MAKE) clean
	./self_signed_certificate.py yaml -f test_self_signed_certificate.yaml
	./self_signed_certificate.py yaml -f test_self_signed_certificate.yaml --verify
	@$(MAKE) clean

cli_test:
	@$(MAKE) clean
	@$(MAKE) cli_test_ca
	@$(MAKE) cli_test_ca_srv
	@$(MAKE) clean
	@$(MAKE) cli_test_self_srv
	@$(MAKE) clean

root.pem root.key:
	@echo "--------"
	@echo $@
	@echo "--------"
	./self_signed_certificate.py cli     \
--ca_country_name "UK"                       \
--ca_state_or_province_name "United Kingdom" \
--ca_locality_name "Cambridge"               \
--ca_organization_name  "Self-Signed CA"     \
--ca_common_name        "CLI CA Test"        \
--cert_not_valid_after  9                    \
--ca_key_path           "root.key"           \
--ca_path               "root.pem"           \
$(CA_PASS_OPT)                               \
;

cli_test_ca:root.pem root.key
	openssl x509 -text -noout -in root.pem
	@echo "=================================="
	$(eval A := $(shell openssl x509 -noout -modulus -in root.pem | openssl md5 | cut -d' ' -f 2))
	$(eval B := $(shell openssl rsa -noout -modulus -in root.key $(CA_PASS_OPT_OPENSSL) | openssl md5 | cut -d' ' -f 2))
	if [ "$(A)" == "$(B)" ]; then echo "modulus OK"; else echo "modulus error"; exit 1; fi
	openssl verify -CAfile root.pem  root.pem
	@echo "=================================="

srv.pem srv.key:root.pem
	@echo "--------"
	@echo $@
	@echo "--------"
	./self_signed_certificate.py cli        \
--ca_path               "root.pem"              \
--ca_key_path           "root.key"              \
$(CA_PASS_OPT)                                  \
--cert_country_name "UK"                        \
--cert_state_or_province_name "United Kingdom"  \
--cert_locality_name "Cambridge"                \
--cert_organization_name  "Self-Signed SRV"     \
--cert_common_name        "CLI SRV Test"        \
--cert_not_valid_after  9                       \
--cert_key_path           "srv.key"             \
--cert_path               "srv.pem"             \
--cert_ip  "127.0.0.1" "2001:DB8:1abc::d57:3bbf:cd8e:fe39" \
--cert_dns "foo.bar" "www.foo.bar" \
;

cli_test_ca_srv:srv.pem srv.key
	openssl x509 -text -noout -in srv.pem
	@echo "================================="
	$(eval A := $(shell openssl x509 -noout -modulus -in srv.pem | openssl md5 | cut -d' ' -f 2))
	$(eval B := $(shell openssl rsa -noout -modulus -in srv.key $(CA_PASS_OPT_OPENSSL) | openssl md5 | cut -d' ' -f 2))
	if [ "$(A)" == "$(B)" ]; then echo "modulus OK"; else echo "modulus error"; exit 1; fi
	openssl verify -CAfile root.pem  srv.pem
	@echo "================================="

srv-self.pem srv-self.key:
	@echo "--------"
	@echo $@
	@echo "--------"
	./self_signed_certificate.py cli        \
--cert_country_name "UK"                        \
--cert_state_or_province_name "United Kingdom"  \
--cert_locality_name "Cambridge"                \
--cert_organization_name  "Self-Signed SRV"     \
--cert_common_name        "CLI SRV Test"        \
--cert_not_valid_after  9                       \
--cert_key_path           "srv-self.key"             \
--cert_path               "srv-self.pem"             \
--cert_ip  "127.0.0.1" "2001:DB8:1abc::d57:3bbf:cd8e:fe39" \
--cert_dns "foo.bar" "www.foo.bar" \
;

cli_test_self_srv: srv-self.pem srv-self.key
	openssl x509 -text -noout -in srv-self.pem
	@echo "================================="
	openssl verify -CAfile srv-self.pem srv-self.pem
	$(eval A := $(shell openssl x509 -noout -modulus -in srv-self.pem | openssl md5 | cut -d' ' -f 2))
	$(eval B := $(shell openssl rsa -noout -modulus -in srv-self.key $(CA_PASS_OPT_OPENSSL) | openssl md5 | cut -d' ' -f 2))
	if [ "$(A)" == "$(B)" ]; then echo "modulus OK"; else echo "modulus error"; exit 1; fi
	@echo "================================="

clean:
	$(RM) root.key root.pem srv.key srv.pem srv-self.pem srv-self.key

help:
	@echo make yaml_test
	@echo make cli_test
	@echo make cli_test_ca
	@echo make cli_test_ca_srv
	@echo make cli_test_self_srv
