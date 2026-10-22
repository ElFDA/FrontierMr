# Common settings of the test scripts (source it): the MiSTer to test on.
#   export MISTER_IP=<address of the MiSTer> MISTER_PW=<its root password>
# or put them in tools/fe/env.local.sh (not in git).
[ -f "$(dirname "${BASH_SOURCE[0]}")/env.local.sh" ] && . "$(dirname "${BASH_SOURCE[0]}")/env.local.sh"
: "${MISTER_IP:?set MISTER_IP (address of the MiSTer)}"
: "${MISTER_PW:?set MISTER_PW (root password of the MiSTer)}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=3"
mssh() { sshpass -p "$MISTER_PW" ssh $SSHOPT root@$MISTER_IP "$@"; }
mscp() { sshpass -p "$MISTER_PW" scp $SSHOPT "$@"; }
