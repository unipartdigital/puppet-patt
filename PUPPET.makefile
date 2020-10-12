DESTDIR := $(shell mktemp -d)
PWD := $(CURDIR)

puppet-module:
	mkdir -p $(DESTDIR)/patt/files/patt
	mkdir -m 755 $(DESTDIR)/patt/files/patt/config
	mkdir -m 755 $(DESTDIR)/patt/files/patt/dscripts
	mkdir -m 755 $(DESTDIR)/patt/files/patt/ssh
	mkdir -m 755 $(DESTDIR)/patt/files/patt/misc

	install -m 644 Makefile $(DESTDIR)/patt/files/patt/.
	install -m 644 README.md $(DESTDIR)/patt/files/patt/.

	install -m 644 config/haproxy.cfg.tmpl $(DESTDIR)/patt/files/patt/config
	install -m 644 config/firewall.nft $(DESTDIR)/patt/files/patt/config
	install -m 644 config/postgres-ipv6.yaml $(DESTDIR)/patt/files/patt/config
	install -m 644 config/pg_create_role.tmpl $(DESTDIR)/patt/files/patt/config
	install -m 644 config/pg_create_database.tmpl $(DESTDIR)/patt/files/patt/config

	install -m 644 dscripts/d01.nft.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/d02.dsk2fs.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/d03.repo.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/d10.etcd.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/d20.postgres.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/d25.floating_ip.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/d30.patroni.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/d40.haproxy.sh $(DESTDIR)/patt/files/patt/dscripts/

	install -m 644 dscripts/haproxy_config.py $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/nft_config.py $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/patroni_config.py $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/patroni_info.py $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/ssl_cert_postgres.py $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/ssl_cert_postgres.sh $(DESTDIR)/patt/files/patt/dscripts/
	install -m 644 dscripts/postgres_exec.sh $(DESTDIR)/patt/files/patt/dscripts/


	install -m 755 misc/self_signed_certificate.py $(DESTDIR)/patt/files/patt/misc/
	install -m 644 ip_takeover.py $(DESTDIR)/patt/files/patt/.
	install -m 644 patt.py $(DESTDIR)/patt/files/patt/.
	install -m 755 patt_cli.py $(DESTDIR)/patt/files/patt/.
	install -m 644 patt_etcd.py $(DESTDIR)/patt/files/patt/.
	install -m 644 patt_haproxy.py $(DESTDIR)/patt/files/patt/.
	install -m 644 patt_patroni.py $(DESTDIR)/patt/files/patt/.
	install -m 644 patt_postgres.py $(DESTDIR)/patt/files/patt/.
	install -m 644 patt_syst.py $(DESTDIR)/patt/files/patt/.
	install -m 644 requirements.txt $(DESTDIR)/patt/files/patt/.

	install -m 644 ssh/interactive.py $(DESTDIR)/patt/files/patt/ssh
	install -m 644 ssh/README.md $(DESTDIR)/patt/files/patt/ssh
	install -m 644 ssh/Makefile $(DESTDIR)/patt/files/patt/ssh
	install -m 644 ssh/ssh_client_demo-01.py $(DESTDIR)/patt/files/patt/ssh
	install -m 644 ssh/ssh_client.py $(DESTDIR)/patt/files/patt/ssh

	mkdir -m 0755 -p $(DESTDIR)/patt/manifests/
	mkdir -m 0755 -p $(DESTDIR)/patt/templates/

	install -m 644 puppet/modules/patt/manifests/service.pp $(DESTDIR)/patt/manifests/
	install -m 644 puppet/modules/patt/manifests/config.pp $(DESTDIR)/patt/manifests/
	install -m 644 puppet/modules/patt/manifests/init.pp $(DESTDIR)/patt/manifests/
	install -m 644 puppet/modules/patt/manifests/require.pp $(DESTDIR)/patt/manifests/
	install -m 644 puppet/modules/patt/manifests/install.pp $(DESTDIR)/patt/manifests/
	install -m 644 puppet/modules/patt/manifests/sshkeys.pp $(DESTDIR)/patt/manifests/
	install -m 644 puppet/modules/patt/manifests/packages.pp $(DESTDIR)/patt/manifests/

	install -m 644 puppet/modules/patt/templates/patt.yaml.epp $(DESTDIR)/patt/templates/

# SSH keys
	mkdir -m 1777 -p $(DESTDIR)/patt/ssh-keys/
	echo '*'     >   $(DESTDIR)/patt/ssh-keys/.gitignore
	echo '!*.sh' >>  $(DESTDIR)/patt/ssh-keys/.gitignore
	install -m 755 puppet/modules/patt/ssh-keys/00-generator.sh $(DESTDIR)/patt/ssh-keys/
	install -m 644 puppet/modules/patt/manifests/sshkeys.pp $(DESTDIR)/patt/manifests/

# SSL certs
	mkdir -m 1777 -p $(DESTDIR)/patt/ssl-cert/
	echo '*'     >   $(DESTDIR)/patt/ssl-cert/.gitignore
	echo '!*.sh' >>  $(DESTDIR)/patt/ssl-cert/.gitignore
	echo '!*.py' >>  $(DESTDIR)/patt/ssl-cert/.gitignore
	install -m 755 puppet/modules/patt/ssl-cert/00-generator.sh $(DESTDIR)/patt/ssl-cert/
	install -m 755 misc/self_signed_certificate.py $(DESTDIR)/patt/ssl-cert/
	install -m 644 puppet/modules/patt/manifests/sslcerts.pp $(DESTDIR)/patt/manifests/


patt-puppet.tar.xz: puppet-module
	cd $(DESTDIR) && chmod 0755 . && tar Jcvpf $(PWD)/$@ --owner root --group root .
	rm -rf $(DESTDIR)
	@echo
	@echo "use --preserve-permissions if extracting the archive as non root user"
	@echo
