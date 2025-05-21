# token-portal


## Postgres backend

```sh
cd backend
docker compose -f docker-compose-db.yml exec postgres_db psql -U user1 -d appdb

# See all tables
\d

# list only tables
\dt 

# See details for users table
\d users 
```