#!/bin/bash
# Connect to Cloud SQL Proxy
# Instance: roundtable41-1dc2c:us-central1:roundtable-db

echo "Starting Cloud SQL Proxy..."
echo "Instance: roundtable41-1dc2c:us-central1:roundtable-db"
echo "Listening on: 127.0.0.1:5432"

cloud-sql-proxy roundtable41-1dc2c:us-central1:roundtable-db
