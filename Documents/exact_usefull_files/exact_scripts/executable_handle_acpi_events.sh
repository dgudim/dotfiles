#!/bin/bash

acpi_listen | while read -r line; do
  if echo "${line}" | grep -i -q -E "headphone|lid"; then
    python "$(dirname "$(readlink -f "${0}")")/handle_acpi_event.py" "${line}"
  fi
done
