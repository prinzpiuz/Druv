#!/bin/bash

#this is a program to automaticaly push system wiki
#depends on inotify
cd /configs || exit
/usr/bin/inotifywait -q -m -e CLOSE_WRITE --format="git commit -m 'auto commit:$(date)' %w && git push origin main" /configs | bash
