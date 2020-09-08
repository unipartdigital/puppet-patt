puppet-module:
	mkdir -p $(DESTDIR)/pgcrt/files/pgcrt
	mkdir -m 755 $(DESTDIR)/pgcrt/files/pgcrt/config
	mkdir -m 755 $(DESTDIR)/pgcrt/files/pgcrt/dscripts
	mkdir -m 755 $(DESTDIR)/pgcrt/files/pgcrt/ssh

	install -m 644 Makefile $(DESTDIR)/pgcrt/files/pgcrt/.
	install -m 644 README.md $(DESTDIR)/pgcrt/files/pgcrt/.

	install -m 644 config/haproxy.cfg.tmpl $(DESTDIR)/pgcrt/files/pgcrt/config
	install -m 644 config/firewall.nft $(DESTDIR)/pgcrt/files/pgcrt/config
	install -m 644 config/postgres-ipv6.yaml $(DESTDIR)/pgcrt/files/pgcrt/config

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
	mkdir -m 1777 -p $(DESTDIR)/pgcrt/ssh-keys/
	mkdir -m 0755 -p $(DESTDIR)/pgcrt/templates/

	install -m 644 puppet/modules/pgcrt/manifests/service.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/config.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/init.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/require.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/install.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/sshkeys.pp $(DESTDIR)/pgcrt/manifests/
	install -m 644 puppet/modules/pgcrt/manifests/packages.pp $(DESTDIR)/pgcrt/manifests/

	install -m 755 puppet/modules/pgcrt/ssh-keys/00-generator.sh $(DESTDIR)/pgcrt/ssh-keys/

	install -m 644 puppet/modules/pgcrt/templates/pgcrt.yaml.epp $(DESTDIR)/pgcrt/templates/
