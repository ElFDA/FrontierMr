#!/bin/bash
# Is Frontier based on the latest stable release of MiSTer's Main_MiSTer?
# Frontier follows the upstream RELEASES (the "Release AAAAMMGG" commits), not master:
# a release is published together with the stable cores that update_all installs.
# Usage: tools/fe/upstream_check.sh [--try]
#   (no option)  fetch and report
#   --try        also rebase onto the newest release in a temporary worktree and build
#                (the branch frontier is not touched)
set -e
cd "$(dirname "$0")/../.."
root=$(pwd)

git fetch -q origin
base=$(git merge-base frontier origin/master)
rels=$(git log --reverse --format='%h %ad %s' --date=short origin/master --grep='^Release [0-9]' )
latest=$(echo "$rels" | tail -1)
latest_sha=${latest%% *}
echo "Frontier is based on: $(git log -1 --format='%h %ad %s' --date=short "$base")"
echo "Latest upstream release: $latest"

if ! echo "$rels" | grep -q "^$(git rev-parse --short "$base") "; then
	echo "WARNING: the base is NOT a release commit: the binary may need cores newer than the stable ones."
	echo "         Rebase onto the release: git rebase --onto $latest_sha $(git rev-parse --short "$base") frontier"
fi
if [ "$(git rev-parse "$base")" == "$(git rev-parse "$latest_sha")" ]; then
	echo "OK: nothing to do, Frontier is on the latest release."
	exit 0
fi

echo
echo "New releases since the base:"
echo "$rels" | awk -v b="$(git rev-parse --short "$base")" 'f{print} $1==b{f=1}'
echo
echo "Upstream commits to the files where Frontier has hooks (// FRONTIER), up to the latest release:"
git log --format='  %h %ad %s' --date=short "$base..$latest_sha" -- menu.cpp video.cpp video.h input.cpp fpga_io.cpp Makefile || true

[ "$1" == "--try" ] || { echo; echo "Run with --try to test the rebase and the build."; exit 0; }

wt=$(mktemp -d)
trap 'git worktree remove --force "$wt" 2>/dev/null || true' EXIT
git worktree add -q --detach "$wt" frontier
cd "$wt"
git update-index --assume-unchanged lib/miniz/ChangeLog.md
if ! git rebase -q --onto "$latest_sha" "$base" >/dev/null 2>&1; then
	echo "CONFLICT in: $(git diff --name-only --diff-filter=U | tr '\n' ' ')"
	git rebase --abort
	exit 1
fi
echo "Rebase onto $latest_sha: no conflicts."
# the ARM toolchain: MISTER_GCC_INSTALL_DIR in the environment or in tools/fe/env.local.sh
[ -f "$root/tools/fe/env.local.sh" ] && . "$root/tools/fe/env.local.sh"
: "${MISTER_GCC_INSTALL_DIR:?set MISTER_GCC_INSTALL_DIR (folder of the ARM toolchain)}"
export MISTER_GCC_INSTALL_DIR
. ./setup_default_toolchain.sh >/dev/null 2>&1
if make -j"$(nproc)" 2>&1 | grep -E "warning|error"; then echo "Build: warnings/errors above"; else echo "Build: OK, no warnings."; fi
