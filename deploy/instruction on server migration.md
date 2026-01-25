### Instructions on server migration

1. drop database vpemaster / create database vpemaster
2. flask metadata restore --file /path/to/metadata.sql
3. flask create-admin
4. create the target club
5. flask import-data --file /path/to/club_data.sql --club-no <club_no>
6. test