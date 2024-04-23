network  --bootproto=dhcp --device=link --activate
url --url=http://fedora-serv.inria.fr/miroirs/fedora/$releasever/Everything/x86_64/os
repo --name kubernetes --baseurl=https://packages.cloud.google.com/yum/repos/kubernetes-el7-x86_64

# Root password
rootpw --iscrypted --lock locked


%packages
kubernetes-cni
dracut-live
%end

%post

cat > /etc/liveboot-release << EOF

just to demonstrate the ability to run a regular bash command
from within a kickstart increment

EOF
%end
