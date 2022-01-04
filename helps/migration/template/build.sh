
#
# Using Jinja2, create consistent instructions for migration.
#
# python -m pip install jinja2-cli
# jq: apt install jq
# yq: https://github.com/mikefarah/yq
#

yq eval -o=j values.yaml | jinja2 migrate.md.jinja > migrate.md
