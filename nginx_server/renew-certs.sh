#!/bin/sh
certbot renew --nginx
nginx -s reload