## medication-tracker

### Requirements
- [Git](https://git-scm.com/install/)
- [Docker](https://docs.docker.com/get-started/get-docker/)

### Setup Instructions
1. Clone this repo and `cd` into repo dir
```shell
git clone https://github.com/gokr10/flask-medication-tracker.git medication_tracker
cd medication_tracker
```
2. Build/run with docker
```shell
docker compose up --build
```
3. Run tests in a separate shell
```shell
cd medication_tracker
docker exec -it flask_app pytest -v
```

* The application is now accessible via http://localhost:4000/


* Adminer is running as a docker service as well, so the Postgres database can be viewed by navigating to:
http://localhost:8080/ and inputting PostgreSQL, 'flask_db' as the server, and the login credentials detailed in `.env`
  * The clean up on the tests is disabled, so there is data visible in the db after running the tests


* Note - there is no separate database setup that needs to be done. There's a note about this in `application/__init__.py`


### Design Notes

1. Database Design
   * Details on the attached ERD chart, also viewable [here](https://lucid.app/lucidchart/a15fab22-9cfb-4d87-be10-43cadf426f1a/edit?viewport_loc=-892%2C-403%2C2188%2C1336%2C0_0&invitationId=inv_a1e641ee-4ec2-474c-95c4-22de66ad3927)
   * DDLs also attached
2. API Implementation
   * ORM - SQLAlchemy
     * Better for portability in case db system needs to change in the future 
     * Easier maintainability by wider range of developers vs more SQL specific 
     * Query complexity/performance - fairly straightforward queries, so raw SQL not necessary
   * flask routing assumes json is the content type
3. Expansions/Other Ideas
   * end_date/expiration_date - could add to user_medications to help with history and a medication's active state in relation to a user
   * could store default dosage and frequency info in the medications table, then optional custom dosage in user_medications
4. TODOs
   * I put TODOs inline for parts I didn't get to while trying to stick to the designated time expectation
