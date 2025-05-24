#!/bin/sh
# Replace ${PORT} with actual PORT value in nginx config
envsubst '${PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Start nginx
exec nginx -g 'daemon off;'