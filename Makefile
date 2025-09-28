# =========================
# Digital Twin Makefile
# =========================
# Edit these if your module paths differ.
PY            := poetry run python
WEB ?= dt/webapp/app.py
COLLECTOR ?= dt/collector/main.py
CONTROLLER ?= dt/controller/app.py
DB ?= dt/data/database/app.py

.PHONY: help \
				install-dev install-rpi install-spark install-db install-naked \
				run-dashboard run-collector run-controller run-database \
				test venv \
				clean-env clean-venv clean-pyc \
				update-deps check-deps

# --------
# Help
# --------
help:
	@echo ""
	@echo "Install profiles:"
	@echo "  make install-dev				-> main + dev + db + spark (no rpi)"
	@echo "  make install-rpi				-> main + rpi + db (lean runtime)"
	@echo "  make install-db				-> main + db (no rpi, no spark)"
	@echo "  make install-spark				-> main + spark + db (no rpi)"
	@echo "  make install-naked				-> main only (no optional groups)"
	@echo ""
	@echo "Run targets:"
	@echo "  make run-dashboard				-> Flask app (web dashboard)"
	@echo "  make run-collector				-> sensor polling loop"
	@echo "  make run-collector				-> actuator/controller app"
	@echo "  make run-database				-> database (TS and RDB) app (SQLite/InfluxDB)"
	@echo ""
	@echo "Quality:"
	@echo "  make test					-> run tests with pytest"
	@echo "  make venv					-> activate the poetry venv"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean-env (remove venv + lock) | clean-venv | clean-pyc"
	@echo ""
	@echo "Maintenance:"
	@echo "  make update-deps				-> update dependencies"
	@echo "  make check-deps				-> check dependencies for issues"
	@echo ""


# -------------------------
# Installation profiles
# -------------------------
install-dev:
	poetry install --with dev,db,spark --without rpi

install-rpi:
	poetry install --only main,rpi,db

install-db:
	poetry install --only main,db

install-spark:
	poetry install --only main,spark

install-dev-naked:
	poetry install --without rpi,spark,influxdb --with dev

install-naked:
	poetry install --only main

install-all:
	poetry install



# -------------------------
# Run targets
# -------------------------
run-dashboard:
	$(PY) $(WEB)

run-collector:
	$(PY) $(COLLECTOR)

run-controller:
	$(PY) $(CONTROLLER)

run-database:
	$(PY) $(DB)

# -------------------------
# Quality (optional groups: dev)
# -------------------------
test:
	poetry run pytest -q

venv:
	eval "$(poetry env activate)"

# -------------------------
# Cleanup
# -------------------------
clean-env:
	poetry env remove python || true
	rm -f poetry.lock

clean-venv:
	poetry env remove python || true

clean-pyc:
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# -------------------------
# Maintenance
# -------------------------
update-deps:
	poetry update

check-deps:
	poetry check
