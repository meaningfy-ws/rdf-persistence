## ADDED Requirements

### Requirement: The service is installed with its migrations folder

`install_service` SHALL take the folder of the consumer's migration files as a required argument,
SHALL refuse to build the service when that folder or the toolkit's own does not form one line of
versions ending at the running schema's version, and SHALL answer a request for the data of a
tenant whose migration failed at start-up (its aggregates, files and listings, and a rename,
which writes its root) with status 503 and the problem `tenant-behind`.

#### Scenario: a chain that forks
- **GIVEN** a migrations folder with two files leaving the same version
- **WHEN** the library service is installed
- **THEN** it fails, naming both files, and serves nothing

#### Scenario: a tenant set aside
- **GIVEN** a library service that set one tenant aside at start-up
- **WHEN** a reader lists that tenant's books
- **THEN** the answer is 503 with the problem type `tenant-behind`
