#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$script_dir"

printf '%s\n' 'Fetching latest updates from origin...'
git fetch origin

printf '%s\n' 'Checking out master branch...'
git checkout master

printf '%s\n' 'Resetting local master to origin/master...'
git reset --hard origin/master

printf '%s\n' 'Done! Local master branch is now synced with remote.'
