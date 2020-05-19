#!/bin/bash

# During a DB upgrade, custom changes to the DB might be lost. This script ensures that any changes and the accompying data are imported.
# By being placed in /srv/jupyterhub/ it is also ensured to persist between rebuilds.
# It is assumed that the custom changes to the DB schema are known.
# This script needs to be ran (here within the hub pod) after the possibily breaking version (Helm) upgrade is performed.
# If not run afterwards then functionality will be lost.

sqlite3 /srv/jupyterhub/jupyterhub.sqlite

# Add fields to group table (as needed)

# Import data to custom fields
.mode cvs 
.import group.csv group
.quit
