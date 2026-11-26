# Test — suite, coverage, integration, pre-commit

## Unit tests

```bash
pytest                                   # full suite (no live Dolibarr needed)
pytest --cov=src/dolibarr_mcp --cov-report=term-missing
python3 -m pytest                        # if `pytest` is not on PATH
```

Layout: `tests/test_*.py` (unit, HTTP layer mocked), `tests/integration/` (marked
`@pytest.mark.integration`, skipped without credentials).

## Integration tests

```bash
export DOLIBARR_URL="https://your-dolibarr.example.com/api/index.php"
export DOLIBARR_API_KEY="your-api-key"
pytest -m integration
```

The integration workflow (`.github/workflows/integration.yml`) runs these against a real Dolibarr
instance it provisions in the job. PHP for that instance is pinned to Dolibarr's documented maximum, read
from `htdocs/install/check.php` in the downloaded sources (`$arrayphpmaxversionwarning = array(8, 5, 0);`
on recent sources — warning when the installed PHP is higher; `array(8, 3, 0)` for the `21.0.0` tag used
in CI). The workflow derives `DOLIBARR_MAX_PHP` from that file and fails the job if the installed PHP
exceeds it, so a `DOLIBARR_TEST_REF` bump re-pins PHP automatically.

## Local integration instance (PHP + Docker)

Run the `integration`-marked suite against a real local Dolibarr without touching CI. Two variants;
prefer A on machines where you do not control the host PHP or host ports.

### A. All-Docker (portable)

Everything (MariaDB, Dolibarr, test runner) runs in containers on one Docker network, so no host PHP
version and no host port can conflict:

1. `docker network create dolibarr-ci`
2. `docker run -d --name dolibarr-ci-mariadb --network dolibarr-ci -e MARIADB_ROOT_PASSWORD=dolibarr -e MARIADB_DATABASE=dolibarr mariadb:11.4`
3. Build a PHP image from `php:8.3-cli` (8.3 = the max for the `21.0.0` tag; read the real cap from
   `htdocs/install/check.php`) with `docker-php-ext-install mysqli gd intl zip mbstring curl xml`, mount
   the Dolibarr sources at `/var/www/dolibarr`, and serve
   `php -S 0.0.0.0:8080 -t /var/www/dolibarr/htdocs`.
4. Download the `${DOLIBARR_TEST_REF}` tarball plus `dev/initdemo/mysqldump_dolibarr_<maj>.0.0.sql` into
   the mounted sources (same URLs as `integration.yml`).
5. Inside the PHP container, with `DB_HOST=dolibarr-ci-mariadb`:
   `bash .github/scripts/setup-dolibarr-instance.sh` then
   `DOLIBARR_HTDOCS=... DOLIBARR_API_KEY=... php .github/scripts/enable-api.php`.
6. Run `pytest -m integration` from a Python container on `dolibarr-ci` with
   `DOLIBARR_URL=http://<php-container>:8080/api/index.php` and `DOLIBARR_API_KEY=<key>`.

### B. Host PHP + Docker MariaDB

MariaDB in Docker, Dolibarr served by the host PHP (fast on a dev machine that has PHP):

1. Publish MariaDB on a high loopback port — `3306` is often already taken on dev machines:
   `docker run -d --name dolibarr-ci-mariadb -p 127.0.0.1:33060:3306 -e MARIADB_ROOT_PASSWORD=dolibarr -e MARIADB_DATABASE=dolibarr mariadb:11.4`
2. Grant remote root (the published port presents the client as a remote host):
   `CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'dolibarr'; GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION; FLUSH PRIVILEGES;`
3. If the host has no `mysql` client, shim it with `docker exec -i dolibarr-ci-mariadb mariadb "$@"`,
   rewriting `--port 33060` to `3306` — the mapping exists only on the host side.
4. Download the Dolibarr sources as in variant A, then run the repo scripts with
   `DB_HOST=127.0.0.1 DB_PORT=33060 DOLIBARR_TEST_REF=21.0.0 DOLIBARR_ROOT=<sources> bash .github/scripts/setup-dolibarr-instance.sh`
   and
   `DOLIBARR_HTDOCS=<sources>/htdocs DOLIBARR_API_KEY=ci-integration-test-key php .github/scripts/enable-api.php`.
5. Serve the instance as a background process (use your agent's background-process API, not `nohup ... &`
   inside a blocking shell call): `php -S 127.0.0.1:8080 -t <sources>/htdocs`.
6. A host PHP newer than Dolibarr's cap usually still serves the demo instance, but CI (variant of the
   workflow above) is authoritative — it pins PHP to the cap.

Gotchas observed on a real machine: the REST API auth header for direct `curl` calls is `DOLAPIKEY`
(`DOLIBARR_API_KEY` is only the MCP server's env var); `docker exec` without `-i` silently drops piped
SQL; a host-local MariaDB on `127.0.0.1:3306` shadows the published port, hence port `33060`.

### Sharing one instance across agents

Run ONE shared instance per machine — container `dolibarr-ci-mariadb`, sources under one fixed path, API
on `127.0.0.1:8080` — and let every agent instance use it. Do not spawn a per-agent instance and do not
reset the database between agents. Every agent exports the same
`DOLIBARR_URL=http://127.0.0.1:8080/api/index.php` and `DOLIBARR_API_KEY=ci-integration-test-key` and
runs `pytest -m integration` with a project venv (`pip install -e .[dev]`). Integration tests must use
uniquely named fixtures and clean up after themselves (pattern of the existing tests) so sequential
agents do not collide on the shared database.

## Pre-commit

```bash
pipx install pre-commit && pre-commit install   # one-time
pre-commit run --all-files                       # before pushing
```

Hooks include mdformat (wrap 105), pylint, flake8, black, isort, mypy, codespell, and
`no-commit-to-branch --branch main`. The same hooks run in CI (`.github/workflows/pre-commit.yml`); keep
both green.

## Docker sanity check

```bash
docker compose --profile test up dolibarr-mcp-test   # runs test_connection in a container
```
