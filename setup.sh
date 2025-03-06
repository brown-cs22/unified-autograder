#!/usr/bin/env bash

# This script is run only once, when the autograder zip gets uploaded.
# The idea is that it prepares the docker image, and when a student submits, that image gets cloned
# for the autograding to happen. 

# MikTeX repo
curl -fsSL https://miktex.org/download/key | tee /usr/share/keyrings/miktex-keyring.asc > /dev/null
echo "deb [signed-by=/usr/share/keyrings/miktex-keyring.asc] https://miktex.org/download/ubuntu jammy universe" | tee /etc/apt/sources.list.d/miktex.list

apt update

cd /autograder

apt install -y jq
apt install -y miktex python3 python3-pip python3-dev
pip3 install bs4 requests-toolbelt pypdf

# MikTeX setup
miktexsetup --shared=yes finish
initexmf --admin --set-config-value [MPM]AutoInstall=1

cp source/config.json ./

THIS_REPO=$(jq -r '.this_repo' < config.json)
git clone "https://github.com/$THIS_REPO" "unified_ag_src"
cp source/upload_secrets.json unified_ag_src/
cp unified_ag_src/packages.txt .
mpm --admin --install-some=packages.txt
rm packages.txt

# Skip Lean setup if there is no assignment path

if [ -z "$(jq -r '.assignment_path' < config.json)" ]; then
    echo "Skipping Lean autograder setup"
    touch no_lean
    exit
fi

#########################################
##  LEAN AUTOGRADER SETUP
#########################################

# -sSf means curl should run silently, except for error messages, and HTTP error messages should get converted to command failure.
# sh -s just runs a shell in interactive mode (reading commands from stdin.) The extra arguments become
# positional parameters to the curled script: install elan with lean4 nightly as default toolchain
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --default-toolchain leanprover/lean4:nightly-2023-01-16

LEAN_AUTOGRADER_REPO=$(jq -r '.autograder_repo' < config.json)
git clone "https://github.com/$LEAN_AUTOGRADER_REPO" "lean_ag_src"
cp config.json lean_ag_src
cd lean_ag_src

~/.elan/bin/lake exe cache get 
~/.elan/bin/lake build autograder AutograderTests 
