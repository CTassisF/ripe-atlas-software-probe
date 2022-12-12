%define     git_repo         ripe-atlas-software-probe
%define     build_dirname    %{git_repo}
%define     local_state_dir  /home/atlas
%define     src_prefix_dir   /usr/local/atlas
%define     exec_env         prod
%define     version          %(find . -name VERSION | head -1 | xargs -I {} sh -c "cat {}")

# flag to ignore files installed in builddir but not packaged in the final RPM
%define	    _unpackaged_files_terminate_build	0

# prevent creation of the build ids in /usr/lib -> see https://access.redhat.com/discussions/5045161
%define	    _build_id_links none

Name:	    	ripe-atlas-common
Summary:    	RIPE Atlas probe
Version:    	%{version}
Release:    	1%{?dist}
License:    	RIPE NCC
Group:      	Applications/Internet
Requires:   	sudo %{?el6:daemontools} %{?el7:psmisc} %{?el8:psmisc} openssh-clients iproute %{?el7:sysvinit-tools} %{?el8:procps-ng} net-tools hostname
BuildRequires:	rpm %{?el7:systemd} %{?el8:systemd} openssl-devel autoconf automake libtool make

%description
Essential core assets used in all probe flavours. This package must be installed for a probe to operate as expected.

%package -n ripe-atlas-probe
Summary:	RIPE Atlas Probe Software Essentials
Group:		Applications/Internet
Provides:	atlasswprobe = %{version}-%{release}
Obsoletes:	atlasswprobe < 5080-3%{?dist}
Requires:	ripe-atlas-common

%description -n ripe-atlas-probe
Probe specific files and configurations that form a working software probe.

%prep
echo "Building for probe version: %{version}"

# performing the steps of '%setup' manually since we are pulling from a remote git repo
echo "Cleaning build dir"
cd %{_builddir}
rm -rf %{_builddir}/%{build_dirname}
echo "Getting Sources..."

%{!?git_tag:%define git_tag master}
%{!?git_source:%define git_source https://github.com/RIPE_NCC}

git clone -b %{git_tag} --recursive %{git_source}/%{git_repo}.git %{_builddir}/%{build_dirname}

cd %{_builddir}/%{build_dirname}
%{?git_commit:git checkout %{git_commit}}

%build
cd %{_builddir}/%{build_dirname}
autoreconf -iv
./configure --prefix=%{src_prefix_dir} --localstatedir=%{local_state_dir}
make

%install
cd %{_builddir}/%{build_dirname}
mkdir -p %{buildroot}%{_unitdir}
install -m644 %{_builddir}/%{build_dirname}/bin/atlas.service %{buildroot}%{_unitdir}/atlas.service
make DESTDIR=%{buildroot} install

%clean
#rm -rf %{buildroot}%{src_prefix_dir}/include
#rm -rf %{buildroot}%{src_prefix_dir}/bin/atlas.service
#rm -rf %{_builddir}

%files
%ghost %{src_prefix_dir}/bin/event_rpcgen.py
%ghost %{src_prefix_dir}/include/*
%ghost %{src_prefix_dir}/lib/pkgconfig
%{src_prefix_dir}/bb-13.3
%{src_prefix_dir}/bin/arch
%attr(755, root, root) %{src_prefix_dir}/bin/ATLAS
%attr(755, root, root) %{src_prefix_dir}/bin/reginit.sh
%attr(644, root, root) %{src_prefix_dir}/bin/common-pre.sh
%attr(644, root, root) %{src_prefix_dir}/bin/common.sh
%attr(755, root, root) %{src_prefix_dir}/bin/*.lib.sh
%attr(755, root, root) %{src_prefix_dir}/lib/libevent-2.1.so.7
%attr(755, root, root) %{src_prefix_dir}/lib/libevent-2.1.so.7.0.0
%attr(755, root, root) %{src_prefix_dir}/lib/libevent_openssl-2.1.so.7
%attr(755, root, root) %{src_prefix_dir}/lib/libevent_openssl-2.1.so.7.0.0
%caps(cap_net_raw=ep) %{src_prefix_dir}/bb-13.3/bin/busybox

%files -n ripe-atlas-probe
%attr(644, root, root) %{_unitdir}/atlas.service
%{src_prefix_dir}/etc
%{src_prefix_dir}/state

%pre -n ripe-atlas-probe
systemctl stop atlas 2>&1 1>/dev/null

# TODO: check cgroup and that all processes are stopped when atlas.service stops
killall -9 eooqd eperd perd telnetd 2>/dev/null || :
rm -fr %{local_state_dir}/status %{local_state_dir}/bin/reg_servers.sh

groupadd atlas
GID=$(getent group atlas | cut -d: -f3)
useradd -c atlas -d %{local_state_dir} -g atlas -s /sbin/nologin -u $GID atlas 2>/dev/null
exit 0

%post -n ripe-atlas-probe
#exec 1>/tmp/atlasprobe.out 2>/tmp/atlasprobe.err
#set -x

if [ ! -f %{local_state_dir}/state/mode ]; then
    mkdir -p %{local_state_dir}/state
    echo "%{exec_env}" > %{local_state_dir}/state/mode
fi

# TODO: move to autoconf for generic build
mkdir -p %{local_state_dir}/{bin,crons/{main,2,7},data/{new,oneoff,out/ooq,out/ooq10},run}

cat > %{local_state_dir}/bin/config.sh << EOF
DEVICE_NAME=centos-sw-probe
ATLAS_BASE="%{local_state_dir}"
ATLAS_STATIC="%{src_prefix_dir}"
SUB_ARCH="centos-rpm-%{name}-%{version}-%{release}"
EOF

chown -R atlas:atlas %{local_state_dir}
find %{local_state_dir} -type d -exec chmod -R 755 {} +
find %{local_state_dir} -type f -exec chmod -R 644 {} +
chmod 600 %{local_state_dir}/etc/probe_key

systemctl --now --quiet enable atlas
exit 0

%preun -n ripe-atlas-probe
if [ $1 -eq 0 ]; then
    # uninstall, otherwise upgrade
    systemctl --now --quiet disable atlas
fi
exit 0

%postun -n ripe-atlas-probe
if [ $1 -eq 0 ]; then
        %{?el7:%systemd_postun}
        %{?el8:%systemd_postun}
        rm -fr %{local_state_dir}
fi
exit 0
