# =========================
# Digital Twin Makefile
# =========================
# Edit these if your module paths differ.
PY            := poetry run python -m
WEB ?= dt.webapp.app
COLLECTOR ?= dt.collector.main
CONTROLLER ?= dt.controller.app
DB ?= dt.data.database.app
PREPROCESS ?= dt.data.preprocess.main
ALERTS ?= dt.analytics.app
IMAGE_ANALYSIS ?= dt.image.image_analysis_service

.PHONY: help \
				install-dev install-rpi install-spark install-db install-naked \
				run-dashboard run-collector run-controller run-database run-preprocessing run-alert-engine run-image-analysis \
				tmux-stack-start tmux-stack-attach tmux-stack-status tmux-stack-stop \
				build-webapp test venv \
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
	@echo "  make run-controller				-> actuator/controller app"
	@echo "  make run-database				-> database (TS and RDB) app (SQLite/InfluxDB)"
	@echo "  make run-preprocessing			-> Spark preprocessing pipeline"
	@echo "  make run-alert-engine				-> alert engine service (Kafka + Flask API)"
	@echo "  make run-image-analysis			-> camera image analysis service (camera_image.raw -> green_ratio.raw)"
	@echo "  make run-alert-api-only			-> alert engine Flask API only (no Kafka consumer)"
	@echo "  make tmux-stack-start				-> launch the SSH-friendly tmux stack"
	@echo "  make tmux-stack-attach				-> attach to the tmux stack session"
	@echo "  make tmux-stack-status				-> inspect tmux stack state and logs"
	@echo "  make tmux-stack-stop				-> stop the tmux stack session"
	@echo "  make build-webapp				-> build Svelte UI into dt/webapp/static/ui"
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

run-preprocessing:
	$(PY) $(PREPROCESS)

run-alert-engine:
	$(PY) $(ALERTS)

run-image-analysis:
	$(PY) $(IMAGE_ANALYSIS)

run-alert-api-only:
	$(PY) -c "from dt.analytics.app import create_app; app=create_app(start_consumer=False); app.run(host='0.0.0.0', port=5003)"

tmux-stack-start:
	poetry run python -m dt.utils.tmux_stack start

tmux-stack-attach:
	poetry run python -m dt.utils.tmux_stack attach

tmux-stack-status:
	poetry run python -m dt.utils.tmux_stack status

tmux-stack-stop:
	poetry run python -m dt.utils.tmux_stack stop

build-webapp:
	npm --prefix dt/webapp/frontend install
	npm --prefix dt/webapp/frontend run build

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
