#!/usr/bin/env bash
set -euo pipefail
export RUN_DB_LAYER_TESTS=1
pytest tests/integration/test_patient_appointment_database_workflow.py
