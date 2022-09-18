#!/bin/bash
REMOTE="$(git remote -v | awk '{ print $2 }' | head -1)"
if [ -n "${GITHUB_TOKEN}" ]
then
    REMOTE=$(echo "${REMOTE}" | sed 's!!https://!https://'"rzuckerm:${GITHUB_TOKEN}"'@!')
fi

set -x
cd "$1"
git init .
git config user.email "automation@example.com"
git config user.name "Automation"
set +x
git remote add origin "${REMOTE}"
set -x
git add .
git commit -m "Generated documentation"
git push -f origin master:gh-pages
