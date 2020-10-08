DESTDIR := $(shell mktemp -d)
PWD := $(CURDIR)

puppet-module:
	mkdir -p $(DESTDIR)/pgcrt/files/pgcrt
	mkdir -m 755 $(DESTDIR)/pgcrt/files/pgcrt/config
	mkdir -m 755 $(DESTDIR)/pgcrt/files/pgcrt/dscripts
	mkdir -m 755 $(DESTDIR)/pgcrt/files/pgcrt/ssh
	mkdir -m 755 $(DESTDIR)/pgcrt/files/pgcrt/misc

	install -m 644 Makefile $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 README.md $(DESTDIR)/pgcrt/files/pgcrt/.

	install -m 644 config/haproxy.cfg.tmpl $(DESTDIR)/pgcrt/files/pgcrt/config
	install -m 644 config/firewall.nft $(DESTDIR)/pgcrt/files/pgcrt/config
	install -m 644 config/postgres-ipv6.yaml $(DESTDIR)/pgcrt/files/pgcrt/config
	install -m 644 config/pg_create_role.tmpl $(DESTDIR)/pgcrt/files/pgcrt/config
	install -m 644 config/pg_create_database.tmpl $(DESTDIR)/pgcrt/files/pgcrt/config

	install -m 644 dscripts/d01.nft.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/d02.dsk2fs.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/d03.repo.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/d10.etcd.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/d20.postgres.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/d25.floating_ip.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/d30.patroni.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/d40.haproxy.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/

	install -m 644 dscripts/haproxy_config.py $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/nft_config.py $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/patroni_config.py $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/patroni_info.py $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/ssl_cert_postgres.py $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/ssl_cert_postgres.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/
	install -m 644 dscripts/postgres_exec.sh $(DESTDIR)/pgcrt/files/pgcrt/dscripts/


	install -m 755 misc/self_signed_certificate.py $(DESTDIR)/pgcrt/files/pgcrt/misc/
	install -m 644 ip_takeover.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 pgcrt.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 755 pgcrt_cli.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 pgcrt_etcd.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 pgcrt_haproxy.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 pgcrt_patroni.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 pgcrt_postgres.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 pgcrt_syst.py $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 requirements.txt $(DESTDIR)/pgcrt/files/pgcrt/.

	install -m 644 ssh/interactive.py $(DESTDIR)/pgcrt/files/pgcrt/ssh
	install -m 644 ssh/README.md $(DESTDIR)/pgcrt/files/pgcrt/ssh
	install -m 644 ssh/Makefile $(DESTDIR)/pgcrt/files/pgcrt/ssh
	install -m 644 ssh/ssh_client_demo-01.py $(DESTDIR)/pgcrt/files/pgcrt/ssh
	install -m 644 ssh/ssh_client.py $(DESTDIR)/pgcrt/files/pgcrt/ssh

	mkdir -m 0755 -p $(DESTDIR)/pgcrt/manifests/
	mkdir -m 0755 -p $(DESTDIR)/pgcrt/templates/

	install -m 644 puppet/modules/pgcrt/manifests/service.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/config.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/init.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/require.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/install.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/sshkeys.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/packages.pp $(DESTDIR)/pgcrt/manifests/

	install -m 644 puppet/modules/pgcrt/templates/pgcrt.yaml.epp $(DESTDIR)/pgcrt/templates/

# SSH keys
	mkdir -m 1777 -p $(DESTDIR)/pgcrt/ssh-keys/
	echo '*'     >   $(DESTDIR)/pgcrt/ssh-keys/.gitignore
	echo '!*.sh' >>  $(DESTDIR)/pgcrt/ssh-keys/.gitignore
	install -m 755 puppet/modules/pgcrt/ssh-keys/00-generator.sh $(DESTDIR)/pgcrt/ssh-keys/
	install -m 644 puppet/modules/pgcrt/manifests/sshkeys.pp $(DESTDIR)/pgcrt/manifests/

# SSL certs
	mkdir -m 1777 -p $(DESTDIR)/pgcrt/ssl-cert/
	echo '*'     >   $(DESTDIR)/pgcrt/ssl-cert/.gitignore
	echo '!*.sh' >>  $(DESTDIR)/pgcrt/ssl-cert/.gitignore
	echo '!*.py' >>  $(DESTDIR)/pgcrt/ssl-cert/.gitignore
	install -m 755 puppet/modules/pgcrt/ssl-cert/00-generator.sh $(DESTDIR)/pgcrt/ssl-cert/
	install -m 755 misc/self_signed_certificate.py $(DESTDIR)/pgcrt/ssl-cert/
	install -m 644 puppet/modules/pgcrt/manifests/sslcerts.pp $(DESTDIR)/pgcrt/manifests/


pgcrt-puppet.tar.xz: puppet-module
	cd $(DESTDIR) && chmod 0755 . && tar Jcvpf $(PWD)/$@ --owner root --group root .
	rm -rf $(DESTDIR)
	@echo
	@echo "use --preserve-permissions if extracting the archive as non root user"
	@echo
