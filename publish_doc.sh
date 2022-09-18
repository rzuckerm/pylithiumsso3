#!/bin/bash
REMOTE="$(git remote -v | awk '{ print $2 }' | head -1)"
set -x
cd "$1"
git init .
git config user.email "automation@example.com"
git config user.name "Automation"
git remote add origin "${REMOTE}"
git add .
git commit -m "Generated documentation"
git push -f origin master:gh-pages
