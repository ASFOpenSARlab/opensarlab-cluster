#!/bin/bash

# During a DB upgrade, custom changes to the DB might be lost. This script ensures that any changes and the accompying data are saved.
# By being placed in /srv/jupyterhub/ it is also ensured to persist between rebuilds.
# It is assumed that the custom changes to the DB schema are known.
# This script needs to be ran (here within the hub pod) before the possibily breaking version (Helm) upgrade is performed.
# If not run beforehand then functionality could be lost forever.

sqlite3 /srv/jupyterhub/jupyterhub.sqlite

# Export data from group table
.header on
.mode csv
.output groups.csv
SELECT * FROM groups;
.quit
